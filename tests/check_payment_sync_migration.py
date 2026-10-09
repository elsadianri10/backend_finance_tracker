"""Validate additive 017 in a synthetic schema; --apply preserves existing data."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from app.config.db_config import engine
from app.models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def baseline_016(sql):
    for line in ('\tdebt_id UUID,\n', '\tdebt_payment_id UUID,\n', '\trequest_hash VARCHAR(64),\n',
                 '\tCONSTRAINT uq_ledger_debt_payment UNIQUE (debt_payment_id),\n',
                 '\tCONSTRAINT uq_ledger_request UNIQUE (user_id, request_id),\n'):
        sql = sql.replace(line, '')
    # request_id is required in other tables; remove only the ledger's new field.
    start = sql.index('CREATE TABLE IF NOT EXISTS ledger_transactions')
    sql = sql[:start] + sql[start:].replace('\trequest_id UUID,\n', '', 1)
    sql = sql.replace(',\n\tFOREIGN KEY(debt_id) REFERENCES debts (id) ON DELETE SET NULL', '')
    sql = sql.replace(',\n\tFOREIGN KEY(debt_payment_id) REFERENCES debt_payments (id) ON DELETE SET NULL', '')
    sql = sql.replace("('ledger_transactions', 'request_hash'),\n        ", '')
    return sql


async def check(apply=False):
    schema = None
    async with engine.connect() as conn:
        raw = (await conn.get_raw_connection()).driver_connection
        try:
            if not apply:
                schema = 'payment_sync_test_' + uuid4().hex
                await raw.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
                init = baseline_016((ROOT / 'database/000_init.sql').read_text(encoding='utf-8'))
                await raw.execute(init.replace("set_config('finance_tracker.reset', 'on', true)", "set_config('finance_tracker.reset', 'off', true)"))
                owner, plan, payment = uuid4(), uuid4(), uuid4()
                await raw.execute("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES($1,'synthetic','synthetic@example.test','Synthetic',NOW())", owner)
                await raw.execute("INSERT INTO routine_plans(id,user_id,kind,recipient,name,amount,status,first_due_date,interval_months,total_cycles,initial_paid,notes,version) VALUES($1,$2,'CONTRIBUTION','Family','Existing',1000,'ACTIVE','2026-10-01',1,12,0,'',3)", plan, owner)
                await raw.execute("INSERT INTO routine_payments(id,plan_id,request_id,sequence,due_date) VALUES($1,$2,$3,1,'2026-10-01')", payment, plan, uuid4())
                await raw.execute("INSERT INTO ledger_transactions(id,user_id,kind,category,description,amount,transaction_date,source_label,destination_label,notes,routine_payment_id) VALUES($1,$2,'expense','family','Existing',1000,'2026-10-01','','','',$3)", uuid4(), owner, payment)
            tables = sorted(Base.metadata.tables)
            await raw.execute('BEGIN')
            for table in tables:
                await raw.execute(f'LOCK TABLE {table} IN SHARE MODE')
            columns = {table: [row['column_name'] for row in await raw.fetch('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=$1 ORDER BY ordinal_position', table)] for table in tables}
            before = {table: await raw.fetch(f'SELECT * FROM {table} ORDER BY 1,2' if len(columns[table]) > 1 else f'SELECT * FROM {table} ORDER BY 1') for table in tables}
            migration = (ROOT / 'database/017_payment_sync.sql').read_text(encoding='utf-8').replace('BEGIN;', '').replace('COMMIT;', '')
            await raw.execute(migration)
            after = {table: await raw.fetch('SELECT ' + ','.join('"' + col + '"' for col in columns[table]) + f' FROM {table} ORDER BY 1,2') for table in tables}
            assert before == after, 'Existing records changed'
            assert not await raw.fetchval("SELECT COUNT(*) FROM ledger_transactions WHERE debt_payment_id IS NOT NULL OR request_hash IS NOT NULL OR request_id IS NOT NULL")
            assert not await raw.fetchval("SELECT COUNT(*) FROM routine_plans WHERE debt_id IS NOT NULL")
            await raw.execute('COMMIT')
            print('PASS: migration 017, all existing columns/records unchanged; no historical backfill or reset.')
            if not apply:
                await raw.execute("UPDATE ledger_transactions SET request_id=$1,request_hash='synthetic'", uuid4())
                await raw.execute("UPDATE ledger_transactions SET debt_payment_id=$1", None)
                print('PASS: new relational columns available on existing payment/ledger rows.')
                from app.schemas.routine_schema import RoutineInput, TransactionInput
                from app.services import routine_service
                async with AsyncSession(bind=conn,expire_on_commit=False) as db:
                    plan=await routine_service.save_plan(RoutineInput(Kind='CONTRIBUTION',Recipient='Synthetic',Name='Concurrent',Amount=1000,FirstDueDate='2026-10-09'),owner,'2026-10',db)
                payload=TransactionInput(RequestId=uuid4(),Kind='expense',Description='Concurrent payment',Category='family',Amount=1000,TransactionDate='2026-10-09',RoutinePlanId=plan['Id'],RoutineSequence=1)
                async def submit():
                    async with engine.connect() as payment_conn:
                        await payment_conn.execute(text(f'SET search_path TO "{schema}"'))
                        await payment_conn.commit()
                        async with AsyncSession(bind=payment_conn,expire_on_commit=False) as payment_db:
                            return await routine_service.save_transaction(payload,owner,payment_db)
                results=await asyncio.gather(submit(),submit())
                assert results[0]['Id']==results[1]['Id']
                assert await raw.fetchval('SELECT COUNT(*) FROM ledger_transactions WHERE request_id=$1',payload.request_id)==1
                print('PASS: concurrent PostgreSQL submissions produce exactly one payment/ledger.')
        finally:
            await raw.execute('ROLLBACK')
            if schema:
                await raw.execute(f'SET search_path TO public; DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(check('--apply' in sys.argv))
