"""026 and baseline/reset verification ONLY in a unique disposable schema."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine, snapshot

async def check():
    schema='access_test_'+uuid4().hex
    async with engine.connect() as connection:
        db=(await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline=(ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            await db.execute(baseline.replace("set_config('finance_tracker.reset', 'on', true)","set_config('finance_tracker.reset', 'off', true)"))
            await db.execute('DROP TABLE access_audit, account_access')
            owner=uuid4()
            await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic-access','owner@example.test','Owner',NOW())",owner)
            await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,interest_type,interest_rate) VALUES($1,$2,'DEBT','Synthetic',2000000,'2026-10-01','NONE',0)",uuid4(),owner)
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            upgrade=(ROOT/'database/026_account_access.sql').read_text(encoding='utf-8')
            await db.execute(upgrade);await db.execute(upgrade)
            assert before==await snapshot(db,tables)
            await db.execute('INSERT INTO account_access(user_id,complimentary,version) VALUES($1,true,1)',owner)
            await db.execute("INSERT INTO access_audit(id,user_id,actor_id,action,reason) VALUES($1,$2,$2,'GRANT','Synthetic grant')",uuid4(),owner)
            populated=await snapshot(db,tables+['account_access','access_audit'])
            await db.execute(upgrade)
            assert populated==await snapshot(db,tables+['account_access','access_audit'])
            await db.execute((ROOT/'database/027_account_trial.sql').read_text(encoding='utf-8'))
            populated=await snapshot(db,tables+['account_access','access_audit'])
            await db.execute(baseline.replace("set_config('finance_tracker.reset', 'on', true)","set_config('finance_tracker.reset', 'off', true)"))
            assert populated==await snapshot(db,tables+['account_access','access_audit'])
            await db.execute(baseline)
            for table in ('users','debts','account_access','access_audit'):
                assert await db.fetchval(f'SELECT COUNT(*) FROM "{table}"')==0
            print('PASS: 026 additive/repeated, all previous rows preserved, grants/audit preserved on repeat/init, reset verified only in synthetic schema.')
        finally:
            await db.execute('ROLLBACK')
            await db.execute('SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()

if __name__=='__main__':asyncio.run(check())
