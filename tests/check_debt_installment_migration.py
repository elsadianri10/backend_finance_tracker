"""Check 019 in a synthetic schema; --apply backs up and verifies real records."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from app.config.db_config import engine


async def snapshot(db, tables, omit_legacy=False):
    result = {}
    for table in tables:
        columns = await db.fetch(
            'SELECT column_name FROM information_schema.columns '
            'WHERE table_schema=current_schema() AND table_name=$1 ORDER BY ordinal_position', table)
        names = [row['column_name'] for row in columns
                 if not (omit_legacy and table == 'debts' and row['column_name'] == 'installment_amounts')]
        query = ','.join('"' + name + '"' for name in names)
        result[table] = [dict(row) for row in await db.fetch(f'SELECT {query} FROM "{table}" ORDER BY 1,2')]
    return result


async def check(apply=False):
    schema = None
    sql = (ROOT / 'database/019_debt_installments_relational.sql').read_text(encoding='utf-8')
    async with engine.connect() as conn:
        db = (await conn.get_raw_connection()).driver_connection
        try:
            if not apply:
                schema = 'debt_relational_test_' + uuid4().hex
                await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
                baseline = (ROOT / 'database/000_init.sql').read_text(encoding='utf-8')
                await db.execute(baseline.replace("set_config('finance_tracker.reset', 'on', true)",
                                                 "set_config('finance_tracker.reset', 'off', true)"))
                # Restore only the historical column layout in this synthetic schema.
                await db.execute("DROP TABLE debt_installments; ALTER TABLE debts ADD COLUMN installment_amounts JSON NOT NULL DEFAULT '[]'")
                owner = uuid4()
                await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic','synthetic@example.test','Synthetic',NOW())", owner)
                for kind, amounts in [('DEBT', [333, 667]), ('RECEIVABLE', [1000]), ('DEBT', [])]:
                    debt = uuid4()
                    await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,due_date,interest_type,interest_rate,installment_count,installment_amounts) VALUES($1,$2,$3,'Synthetic',1000,'2026-01-01','2026-02-01','NONE',0,$4,$5::json)",
                                     debt, owner, kind, len(amounts), json.dumps(amounts))
                    await db.execute("INSERT INTO debt_payments(id,debt_id,request_id,sequence,amount,payment_date) VALUES($1,$2,$3,1,100,'2026-01-02')", uuid4(), debt, uuid4())
                # Invalid legacy data must roll back table creation and retain JSON.
                await db.execute("UPDATE debts SET installment_amounts='[1]' WHERE installment_count=0")
                try:
                    await db.execute(sql)
                except Exception:
                    await db.execute('ROLLBACK')
                else:
                    raise AssertionError('Invalid legacy data accepted')
                assert await db.fetchval("SELECT to_regclass('debt_installments')") is None
                await db.execute("UPDATE debts SET installment_amounts='[]' WHERE installment_count=0")
            await db.execute('BEGIN')
            tables = [row['tablename'] for row in await db.fetch(
                'SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            if 'debt_installments' in tables:
                raise RuntimeError('019 already applied; no changes made')
            for table in tables:
                await db.execute(f'LOCK TABLE "{table}" IN SHARE MODE')
            before = await snapshot(db, tables)
            expected = {row['id']: json.loads(row['installment_amounts'])
                        if isinstance(row['installment_amounts'], str) else row['installment_amounts']
                        for row in before['debts']}
            unchanged = {table: [dict(row) for row in rows] for table, rows in before.items()}
            for row in unchanged['debts']:
                row.pop('installment_amounts')
            if apply:
                backup_dir = ROOT / '.migration-backups'
                backup_dir.mkdir(exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                (backup_dir / f'debt-019-{stamp}.json').write_text(
                    json.dumps(before, default=str, ensure_ascii=False, indent=2), encoding='utf-8')
            await db.execute(sql.replace('BEGIN;', '').replace('COMMIT;', ''))
            assert unchanged == await snapshot(db, tables, omit_legacy=True), 'Existing records changed'
            for debt, amounts in expected.items():
                rows = await db.fetch('SELECT amount FROM debt_installments WHERE debt_id=$1 ORDER BY sequence', debt)
                assert amounts == [int(row['amount']) for row in rows], 'Installment order/amounts changed'
            assert not await db.fetchval("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=current_schema() AND data_type IN ('json','jsonb')"), 'JSON columns remain'
            await db.execute('COMMIT')
            print(f'PASS: 019 preserves all records and ordered installment amounts ({len(expected)} debts); no JSON/JSONB columns remain.')
            if schema:
                # New normalized schema is readable by the ORM and existing ledger.
                from sqlalchemy import select
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.models import Debt
                from app.services.debt_service import ledger, payments_for
                async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                    for debt in await session.scalars(select(Debt)):
                        result = ledger(debt, await payments_for(debt, session))
                        assert result['RemainingAmount'] == 900
                        assert [r['PrincipalAmount'] for r in result['Installments']] == expected[debt.id]
                print('PASS: PostgreSQL ORM reads preserve installment schedule and balances.')
        finally:
            await db.execute('ROLLBACK')
            if schema:
                await db.execute(f'SET search_path TO public; DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check('--apply' in sys.argv))
