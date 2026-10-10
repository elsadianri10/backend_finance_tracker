"""Check init/reset in a random PostgreSQL schema; never reset the app schema."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import engine
from app.models import Base


async def check():
    schema = 'baseline_test_' + uuid4().hex
    reset = Path('database/000_init.sql').read_text(encoding='utf-8')
    sql = reset.replace("set_config('finance_tracker.reset', 'on', true)", "set_config('finance_tracker.reset', 'off', true)")
    assert reset != sql
    assert 'TRUNCATE TABLE' in reset and 'DROP TABLE' not in reset
    async with engine.connect() as connection:
        raw = await connection.get_raw_connection()
        db = raw.driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"')
        try:
            await db.execute(f'SET search_path TO "{schema}"')
            await db.execute(sql)
            for table in Base.metadata.sorted_tables:
                rows = await db.fetch('SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema=$1 AND table_name=$2', schema, table.name)
                assert {r['column_name']: r['is_nullable'] == 'YES' for r in rows} == {c.name: c.nullable for c in table.columns}, table.name
            assert await db.fetchval('SELECT COUNT(*) FROM wallet_providers') == 7
            assert await db.fetchval("SELECT to_regclass('billing_platform_types')") is None
            await db.execute('CREATE TABLE baseline_sentinel (value INTEGER)')
            await db.execute('INSERT INTO baseline_sentinel VALUES (42)')
            user, account, transaction, bill = [uuid4() for _ in range(4)]
            await db.execute("INSERT INTO users(id, google_sub, email, name, last_login_at) VALUES($1, 'synthetic', 'synthetic@example.test', 'Synthetic', NOW())", user)
            await db.execute("INSERT INTO billing_accounts(id,user_id,platform_id,platform_type,has_fixed_bill_date) VALUES($1,$2,1,'PAY_LATER',false)", account, user)
            await db.execute("INSERT INTO billing_transactions(id,account_id,description,tenor,transaction_date,first_installment,transaction_kind,amount) VALUES($1,$2,'Synthetic',0,'2026-10-05','2026-10-05','SUBSCRIPTION',15000)", transaction, account)
            await db.execute("INSERT INTO billing_installments(id,transaction_id,sequence,amount,due_date,charged_on) VALUES($1,$2,25,15000,'2028-10-05','2028-10-05')", bill, transaction)
            debt_id, debt_payment_id = uuid4(), uuid4()
            await db.execute("INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,interest_type,interest_rate) VALUES($1,$2,'DEBT','Synthetic',1000,'2026-10-01','NONE',0)",debt_id,user)
            await db.execute("INSERT INTO debt_payments(id,debt_id,request_id,sequence,amount,payment_date) VALUES($1,$2,$3,1,500,'2026-10-02')",debt_payment_id,debt_id,uuid4())
            await db.execute("UPDATE debts SET installment_count=2,due_date='2026-11-01' WHERE id=$1", debt_id)
            await db.execute("INSERT INTO debt_installments(debt_id,sequence,amount) VALUES($1,1,333),($1,2,667)", debt_id)
            await db.execute("INSERT INTO bank_accounts(id,user_id,platform_id,account_number_encrypted,card_number_encrypted,valid_thru,admin_fee,others_fee) VALUES($1,$2,1,'synthetic-account-ciphertext','synthetic-card-ciphertext','2029-07',15000,0)",uuid4(),user)
            await db.execute("INSERT INTO split_bill_groups(id,user_id,name,start_date,end_date,version) VALUES($1,$2,'Synthetic','2026-10-01','2026-10-31',1)",uuid4(),user)
            saving_id = uuid4()
            await db.execute("INSERT INTO savings(id,user_id,kind,name,opening_amount,start_date,notes) VALUES($1,$2,'CASH','Synthetic',1000,'2026-10-01','')",saving_id,user)
            await db.execute("INSERT INTO saving_movements(id,saving_id,request_id,sequence,direction,amount,movement_date,notes) VALUES($1,$2,$3,1,'ADD',500,'2026-10-02','')",uuid4(),saving_id,uuid4())
            routine_id, payment_id = uuid4(), uuid4()
            await db.execute("INSERT INTO routine_plans(id,user_id,kind,recipient,name,amount,status,first_due_date,interval_months,total_cycles,initial_paid,notes,version) VALUES($1,$2,'CONTRIBUTION','Synthetic','Routine',1000,'ACTIVE','2026-10-01',1,12,0,'',1)",routine_id,user)
            await db.execute("INSERT INTO routine_payments(id,plan_id,request_id,sequence,due_date) VALUES($1,$2,$3,1,'2026-10-01')",payment_id,routine_id,uuid4())
            await db.execute("INSERT INTO ledger_transactions(id,user_id,kind,category,description,amount,transaction_date,notes,source_label,destination_label,routine_payment_id) VALUES($1,$2,'expense','family','Synthetic routine',1000,'2026-10-01','','','',$3)",uuid4(),user,payment_id)
            await db.execute("INSERT INTO transaction_imports(user_id) VALUES($1)",user)
            await db.execute(sql)
            assert await db.fetchval('SELECT COUNT(*) FROM split_bill_groups') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM savings') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM saving_movements') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM bank_accounts') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM debt_payments') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM debt_installments') == 2
            assert await db.fetchval('SELECT COUNT(*) FROM users') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM billing_installments') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM wallet_providers') == 7
            for table in ('routine_plans', 'routine_payments', 'ledger_transactions', 'transaction_imports'):
                assert await db.fetchval(f'SELECT COUNT(*) FROM {table}') == 1
            await db.execute('CREATE TABLE billing_platform_types(platform_id INTEGER REFERENCES wallet_providers(id))')
            try:
                await db.execute(sql)
                raise AssertionError('Old billing schema must require migration')
            except asyncpg.RaiseError as error:
                assert 'migration' in str(error)
                await db.execute('ROLLBACK')
            assert await db.fetchval('SELECT COUNT(*) FROM users') == 1
            assert await db.fetchval('SELECT COUNT(*) FROM billing_installments') == 1
            await db.execute('DROP TABLE billing_platform_types')
            await db.execute("UPDATE wallet_providers SET name='Custom BCA', is_active=false WHERE id=1")
            await db.execute("INSERT INTO wallet_providers(id,name,is_active) VALUES(99,'Custom Platform',false)")
            platforms_before = await db.fetch('SELECT * FROM wallet_providers ORDER BY id')
            await db.execute(reset)
            assert await db.fetchval('SELECT COUNT(*) FROM debt_installments') == 0
            for table in ('ledger_transactions', 'routine_payments', 'routine_plans', 'transaction_imports', 'split_bill_shares', 'split_bill_items', 'split_bill_expenses', 'split_bill_participants', 'split_bill_groups', 'saving_movements', 'savings', 'bank_accounts', 'users', 'billing_accounts', 'billing_transactions', 'billing_installments', 'debts', 'debt_payments'):
                assert await db.fetchval(f'SELECT COUNT(*) FROM {table}') == 0
            assert await db.fetch('SELECT * FROM wallet_providers ORDER BY id') == platforms_before
            assert await db.fetchval('SELECT value FROM baseline_sentinel') == 42
            assert await db.fetchval("SELECT to_regclass('billing_platform_types')") is None
            await db.execute(reset)
            assert await db.fetch('SELECT * FROM wallet_providers ORDER BY id') == platforms_before
            print('PASS: latest ORM schema, 7 seeds, non-destructive optional init, default/repeated TRUNCATE reset, custom platforms/statuses preserved, old schema guard, unrelated table preserved. Only synthetic schema used.')
        finally:
            await db.execute('ROLLBACK')
            await db.execute('SET search_path TO public')
            await db.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check())
