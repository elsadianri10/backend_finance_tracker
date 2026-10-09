"""Test upgrade in an isolated schema, or apply it with backup and equality checks.

Default: synthetic data only. --apply: configured application DB, no reset.
Stop the running API before --apply and restart it after the migration.
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from app.config.db_config import engine
from app.models.split_bill_model import SplitBillGroup
from app.schemas.split_bill_schema import GroupCreate, GroupUpdate
from app.services.split_bill_service import calculate, responses, save, owned, response


def migration_sql():
    sql = (ROOT / 'database/015_split_bill_relational.sql').read_text(encoding='utf-8')
    return sql.replace('\nBEGIN;\n', '\n', 1).removesuffix('COMMIT;\n')


async def migrate(connection, backup=False):
    raw = (await connection.get_raw_connection()).driver_connection
    await connection.execute(text('LOCK TABLE split_bill_groups IN ACCESS EXCLUSIVE MODE'))
    source = list((await connection.execute(text('SELECT id,user_id,document,version,created_at FROM split_bill_groups ORDER BY id'))).mappings())
    expected = {}
    for row in source:
        document = json.loads(row['document']) if isinstance(row['document'], str) else row['document']
        payload = GroupCreate.model_validate(document)
        expected[row['id']] = (payload, calculate(payload), row['user_id'], row['version'], row['created_at'])
    if backup:
        folder = ROOT / '.migration-backups'
        folder.mkdir(exist_ok=True)
        path = folder / ('split-bills-before-015-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        path.write_text(json.dumps([dict(row) for row in source], default=str, ensure_ascii=False), encoding='utf-8')
        print('Backup saved locally in ignored .migration-backups/ (contents not logged).')
    # The caller owns the transaction; verify BEFORE committing the DDL/data.
    await raw.execute(migration_sql())
    async with AsyncSession(bind=connection, expire_on_commit=False) as session:
        groups = list(await session.scalars(select(SplitBillGroup).order_by(SplitBillGroup.id)))
        results = await responses(groups, session)
        assert len(results) == len(expected), 'Group count changed'
        for group, result in zip(groups, results):
            payload, calculation, owner, version, created_at = expected[group.id]
            assert GroupCreate.model_validate({key: value for key, value in result.items() if key not in ('Id', 'Version', 'Calculation')}) == payload, 'Stored data/order changed'
            assert result['Calculation'] == calculation, 'Calculation changed'
            assert (group.user_id, group.version, group.created_at) == (owner, version, created_at), 'Metadata changed'
    assert not await connection.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name LIKE 'split_bill_%' AND data_type IN ('json','jsonb')"))
    return len(expected)


def synthetic_documents():
    people = [{'Id': str(uuid4()), 'Name': name} for name in ('Tirta', 'Élsa', 'Ajeng')]
    shared_item = str(uuid4())
    bill = {'Id': str(uuid4()), 'Name': 'Makan & minum', 'ExpenseDate': '2026-10-09', 'PaidBy': people[1]['Id'],
            'Items': [{'Id': shared_item, 'Name': 'Makan', 'Amount': 150401, 'SplitMode': 'CUSTOM',
                       'Shares': [{'ParticipantId': p['Id'], 'Amount': value} for p, value in zip(reversed(people), (60000, 60000, 30401))]}],
            'ServiceCharge': {'Mode': 'PERCENT', 'Value': '7.25'}, 'Tax': {'Mode': 'PERCENT', 'Value': '10'},
            'FeeAllocation': 'MIXED', 'TaxIncludesService': True, 'ReceiptTotal': 177000, 'Notes': 'Catatan sintetis'}
    second = {'Id': str(uuid4()), 'Name': 'Bentor', 'ExpenseDate': '2026-10-01', 'PaidBy': people[0]['Id'],
              'Items': [{'Id': shared_item, 'Name': 'Bersama', 'Amount': 10000, 'Shares': [{'ParticipantId': p['Id'], 'Amount': 0} for p in people]}],
              'ServiceCharge': {'Mode': 'AMOUNT', 'Value': 0}, 'TaxIncludesService': False, 'FeeAllocation': 'PROPORTIONAL'}
    base = {'Name': 'Data sintetis', 'StartDate': '2026-10-01', 'EndDate': '2026-10-31', 'Participants': people, 'Expenses': [bill, second]}
    return [base, base | {'Name': 'Same IDs in a different group'}, base | {'Name': 'Empty group', 'Expenses': []}]


async def check(apply=False):
    schema = None
    async with engine.connect() as connection:
        try:
            if not apply:
                schema = 'split_migration_test_' + uuid4().hex
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET search_path TO "{schema}"'))
                await connection.execute(text('CREATE TABLE users(id UUID PRIMARY KEY)'))
                raw = (await connection.get_raw_connection()).driver_connection
                await raw.execute((ROOT / 'database/014_split_bills.sql').read_text().replace('BEGIN;', '').replace('COMMIT;', ''))
                owner = uuid4()
                await connection.execute(text('INSERT INTO users(id) VALUES(:id)'), {'id': owner})
                for index, document in enumerate(synthetic_documents()):
                    await connection.execute(text('INSERT INTO split_bill_groups(id,user_id,document,version) VALUES(:id,:user,CAST(:document AS jsonb),:version)'),
                                             {'id': uuid4(), 'user': owner, 'document': json.dumps(document), 'version': index + 3})
                await connection.commit()
                # Force a failure AFTER backfill DDL starts, and verify full rollback.
                async with connection.begin():
                    try:
                        async with connection.begin_nested():
                            await connection.execute(text("UPDATE split_bill_groups SET document=jsonb_set(document,'{Expenses,0,PaidBy}',CAST(:payer AS jsonb)) WHERE jsonb_array_length(document->'Expenses')>0"), {'payer': json.dumps(str(uuid4()))})
                            await raw.execute(migration_sql())
                            raise AssertionError('Invalid payer migration accepted')
                    except Exception as error:
                        if isinstance(error, AssertionError):
                            raise
                        assert 'ForeignKeyViolation' in type(error).__name__, type(error).__name__
                    assert await connection.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='split_bill_groups' AND column_name='document'")) == 1
                    assert await connection.scalar(text("SELECT to_regclass('split_bill_participants')")) is None
                print('PASS: failed SQL backfill rolls back schema and original data.')
            async with connection.begin():
                count = await migrate(connection, backup=apply)
            print(f'PASS: {count} groups migrated; all fields, order, metadata, calculations and transfers identical; no Split Bill JSON/JSONB columns.')
            if not apply:
                groups = list((await connection.execute(text('SELECT id FROM split_bill_groups'))).scalars())
                # A participant in another group must never be used as payer.
                participant = uuid4()
                await connection.execute(text("INSERT INTO split_bill_participants(group_id,id,name,position) VALUES(:g,:p,'Other',3)"), {'g': groups[0], 'p': participant})
                await connection.commit()
                async with connection.begin():
                    try:
                        async with connection.begin_nested():
                            await connection.execute(text('UPDATE split_bill_expenses SET paid_by=:p WHERE group_id=:g'), {'p': participant, 'g': groups[1]})
                            raise AssertionError('Cross-group payer accepted')
                    except Exception as error:
                        if isinstance(error, AssertionError):
                            raise
                        assert 'ForeignKeyViolation' in str(error), type(error).__name__
                print('PASS: PostgreSQL composite FK rejects cross-group payer.')
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    payload = GroupCreate.model_validate(synthetic_documents()[0])
                    created = await save(payload, owner, session)
                    current = await response(await owned(UUID(created['Id']), owner, session), session)
                    assert current == created
                    changed = payload.model_dump(by_alias=True) | {'Version': 1, 'Expenses': [], 'Name': 'Edited synthetic'}
                    updated = await save(GroupUpdate.model_validate(changed), owner, session, UUID(created['Id']))
                    assert updated['Version'] == 2 and updated['Calculation']['Total'] == 0
                    await session.delete(await owned(UUID(created['Id']), owner, session, True))
                    await session.commit()
                print('PASS: PostgreSQL relational create/read/replace/delete and cascade.')
        finally:
            await connection.rollback()
            if schema:
                await connection.execute(text('SET search_path TO public'))
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                await connection.commit()
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check('--apply' in sys.argv))
