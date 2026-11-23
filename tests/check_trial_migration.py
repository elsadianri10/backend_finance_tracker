"""027 upgrade, repeat and baseline checks ONLY in an isolated synthetic schema."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine, snapshot
from synthetic_database import reset_synthetic_schema

async def check():
    schema='trial_test_'+uuid4().hex
    async with engine.connect() as connection:
        db=(await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline=(ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            init=baseline
            await db.execute(init)
            await db.execute('ALTER TABLE account_access DROP CONSTRAINT ck_access_trial_dates, DROP COLUMN trial_started_at, DROP COLUMN trial_until')
            owners=[uuid4() for _ in range(3)]
            for i,owner in enumerate(owners):
                await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,$2,$3,'Synthetic',NOW())",owner,'trial-'+str(i),'trial'+str(i)+'@example.test')
            await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,interest_type,interest_rate) VALUES($1,$2,'DEBT','Synthetic',2000000,'2026-10-01','NONE',0)",uuid4(),owners[0])
            await db.execute('INSERT INTO account_access(user_id,complimentary,version) VALUES($1,true,3)',owners[1])
            await db.execute("INSERT INTO account_access(user_id,subscription_plan,subscription_until,version) VALUES($1,'PRO',NOW()+INTERVAL '90 days',4)",owners[2])
            await db.execute("INSERT INTO access_audit(id,user_id,actor_id,action,reason) VALUES($1,$2,$2,'GRANT','Synthetic')",uuid4(),owners[1])
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() AND tablename<>$1 ORDER BY tablename','account_access')]
            financial=await snapshot(db,tables)
            old=[dict(r) for r in await db.fetch('SELECT * FROM account_access ORDER BY user_id')]
            upgrade=(ROOT/'database/027_account_trial.sql').read_text(encoding='utf-8')
            await db.execute(upgrade)
            assert financial==await snapshot(db,tables)
            records=await db.fetch('SELECT * FROM account_access')
            assert len(records)==3
            for record in records:
                assert record['trial_until']-record['trial_started_at']==timedelta(days=30)
            for original in old:
                updated=next(r for r in records if r['user_id']==original['user_id'])
                for key,value in original.items():
                    assert updated[key]==(value+1 if key=='version' else value)
            await db.execute("UPDATE account_access SET trial_started_at=NOW()-INTERVAL '60 days',trial_until=NOW()-INTERVAL '30 days' WHERE user_id=$1",owners[0])
            before=await snapshot(db,tables+['account_access'])
            await db.execute(upgrade);await db.execute(upgrade)
            assert before==await snapshot(db,tables+['account_access'])
            await db.execute(init)
            assert before==await snapshot(db,tables+['account_access'])
            await reset_synthetic_schema(db, schema)
            for table in ('users','debts','account_access','access_audit'):
                assert await db.fetchval(f'SELECT COUNT(*) FROM "{table}"')==0
            print('PASS: one 30-day trial for existing accounts; financial/grant/paid/audit data preserved; repeat never resets expired trials; baseline/init/reset verified only in synthetic schema.')
        finally:
            await db.execute('ROLLBACK')
            await db.execute('SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()

if __name__=='__main__':asyncio.run(check())
