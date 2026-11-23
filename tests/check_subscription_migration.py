"""028 additive/repeat and baseline/reset verification only in an isolated synthetic schema."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine, snapshot
from synthetic_database import reset_synthetic_schema

async def check():
    schema='subscription_test_'+uuid4().hex
    async with engine.connect() as connection:
        db=(await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            baseline=(ROOT/'database/000_init.sql').read_text(encoding='utf-8')
            preserve=baseline
            await db.execute(preserve)
            await db.execute('DROP TABLE subscription_payments, subscription_orders')
            user, debt, order, payment=uuid4(),uuid4(),uuid4(),uuid4()
            await db.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic-sub','synthetic@example.test','Synthetic',NOW())",user)
            await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,interest_type,interest_rate) VALUES($1,$2,'DEBT','Synthetic',2000000,'2026-10-01','NONE',0)",debt,user)
            await db.execute("INSERT INTO account_access(user_id,complimentary,trial_started_at,trial_until) VALUES($1,true,NOW(),NOW()+interval '720 hours')",user)
            tables=[r['tablename'] for r in await db.fetch('SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename')]
            before=await snapshot(db,tables)
            upgrade=(ROOT/'database/028_subscriptions.sql').read_text(encoding='utf-8')
            await db.execute(upgrade);await db.execute(upgrade)
            assert before==await snapshot(db,tables)
            await db.execute("INSERT INTO subscription_orders(id,user_id,request_id,plan,amount,environment,auto_renew,state,renewal_state) VALUES($1,$2,$3,'MONTHLY',29000,'sandbox',false,'PAID','NONE')",order,user,uuid4())
            await db.execute("INSERT INTO subscription_payments(id,order_id,transaction_id,provider_order_id,environment,amount,state,paid_at,period_start,period_end) VALUES($1,$2,'synthetic-tx','synthetic-order','sandbox',29000,'PAID',NOW(),NOW(),NOW()+interval '1 month')",payment,order)
            tables+=['subscription_orders','subscription_payments']
            populated=await snapshot(db,tables)
            await db.execute(upgrade);await db.execute(preserve)
            assert populated==await snapshot(db,tables)
            for invalid in ["UPDATE subscription_orders SET amount=0", "UPDATE subscription_orders SET auto_renew=true", "UPDATE subscription_orders SET plan='FAKE'"]:
                try:await db.execute(invalid)
                except Exception:pass
                else:raise AssertionError('constraint missing: '+invalid)
            await reset_synthetic_schema(db, schema)
            for table in ('users','debts','account_access','subscription_orders','subscription_payments'):
                assert await db.fetchval(f'SELECT COUNT(*) FROM "{table}"')==0
            print('PASS: 028 upgrade/repeat preserve every old row; populated baseline preserves billing; constraints and synthetic reset verified.')
        finally:
            await db.execute('ROLLBACK');await db.execute('SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()

if __name__=='__main__':asyncio.run(check())
