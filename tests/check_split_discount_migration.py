"""Verify 020 in an isolated schema; --apply backs up and compares all records."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_debt_installment_migration import engine, snapshot


async def check(apply=False):
    schema = None
    async with engine.connect() as conn:
        db = (await conn.get_raw_connection()).driver_connection
        try:
            if not apply:
                schema = 'split_discount_test_' + uuid4().hex
                await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
                baseline = (ROOT / 'database/000_init.sql').read_text(encoding='utf-8')
                baseline = '\n'.join(line for line in baseline.splitlines()
                    if 'discount BIGINT' not in line and 'ck_split_discount' not in line
                    and "('split_bill_expenses', 'discount')" not in line)
                await db.execute(baseline.replace("set_config('finance_tracker.reset', 'on', true)",
                                                 "set_config('finance_tracker.reset', 'off', true)"))
                user, group, payer, other, expense, item = [uuid4() for _ in range(6)]
                await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic','synthetic@example.test','Synthetic',NOW())", user)
                await db.execute("INSERT INTO split_bill_groups(id,user_id,name,start_date,end_date,version) VALUES($1,$2,'Synthetic','2026-10-01','2026-10-31',1)", group, user)
                await db.execute("INSERT INTO split_bill_participants(group_id,id,name,position) VALUES($1,$2,'A',0),($1,$3,'B',1)", group, payer, other)
                await db.execute("INSERT INTO split_bill_expenses(group_id,id,name,expense_date,paid_by,service_mode,service_value,tax_mode,tax_value,tax_includes_service,fee_allocation,notes,position) VALUES($1,$2,'Synthetic','2026-10-12',$3,'AMOUNT',0,'AMOUNT',0,false,'MIXED','',0)", group, expense, payer)
                await db.execute("INSERT INTO split_bill_items(group_id,expense_id,id,name,amount,split_mode,position) VALUES($1,$2,$3,'Food',10000,'EQUAL',0)", group, expense, item)
                await db.execute("INSERT INTO split_bill_shares(group_id,expense_id,item_id,participant_id,amount,position) VALUES($1,$2,$3,$4,0,0),($1,$2,$3,$5,0,1)", group, expense, item, payer, other)
            await db.execute('BEGIN')
            await db.execute("SET LOCAL lock_timeout = '10s'")
            tables = [row['tablename'] for row in await db.fetch(
                'SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            for table in tables:
                await db.execute(f'LOCK TABLE "{table}" IN SHARE MODE')
            before = await snapshot(db, tables)
            if await db.fetchval("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='split_bill_expenses' AND column_name='discount'"):
                raise RuntimeError('020 already applied; no changes made')
            if apply:
                backup = ROOT / '.migration-backups'
                backup.mkdir(exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                (backup / f'split-discount-020-{stamp}.json').write_text(
                    json.dumps(before, default=str, ensure_ascii=False, indent=2), encoding='utf-8')
            sql = (ROOT / 'database/020_split_bill_discount.sql').read_text(encoding='utf-8')
            await db.execute(sql.replace('BEGIN;', '').replace('COMMIT;', ''))
            after = await snapshot(db, tables)
            for row in after['split_bill_expenses']:
                assert row.pop('discount') == 0
            assert before == after, 'Existing records changed'
            if schema:
                await db.execute('SAVEPOINT invalid_discount')
                try:
                    await db.execute('UPDATE split_bill_expenses SET discount=-1')
                except Exception:
                    await db.execute('ROLLBACK TO SAVEPOINT invalid_discount')
                else:
                    raise AssertionError('Invalid discount accepted')
            await db.execute('COMMIT')
            print('PASS: 020 preserves all old records; existing expenses have discount 0.')
            if schema:
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.services.split_bill_service import list_groups
                async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                    groups = await list_groups(user, session)
                    assert groups[0]['Calculation']['Total'] == 10000
                    assert groups[0]['Expenses'][0]['Discount'] == 0
                print('PASS: PostgreSQL ORM reads preserve original Split Bill totals.')
        finally:
            await db.execute('ROLLBACK')
            if schema:
                await db.execute(f'SET search_path TO public; DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check('--apply' in sys.argv))
