"""Compare isolated Ringkasan and Transaksi endpoint reads on synthetic PostgreSQL data."""
import argparse
import asyncio
import hashlib
import statistics
import sys
from datetime import date
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')

from app.config.db_config import connect_args, engine, get_db
from app.controllers.auth_controller import get_current_user
from app.models import User
from app.routes.routine_route import router as routine_router
from app.routes.summary_route import router as summary_router

OWNER = UUID(int=1)
MONTH = '2026-10'
AS_OF = date(2026, 11, 23)

SEED_SQL = """
INSERT INTO users(id, google_sub, email, name, last_login_at)
VALUES ('00000000-0000-0000-0000-000000000001','synthetic','synthetic@example.test','Synthetic',now());
INSERT INTO account_access(user_id, complimentary) SELECT id, true FROM users;
INSERT INTO ledger_transactions(id, user_id, kind, category, description, amount, transaction_date, source_label, destination_label, notes)
SELECT md5('ledger' || n)::uuid, u.id, 'expense', 'other', 'Synthetic transaction ' || n, 10000+n,
    date '2021-11-01' + (n % 1826), '', '', repeat('x', 40)
FROM users u CROSS JOIN generate_series(1,12000) n;

INSERT INTO savings(id,user_id,kind,name,opening_amount,start_date,notes)
SELECT md5('saving' || n)::uuid, u.id, 'CASH','Synthetic saving ' || n,100000,'2021-11-01',''
FROM users u CROSS JOIN generate_series(1,12) n;
INSERT INTO saving_movements(id,saving_id,request_id,sequence,direction,amount,movement_date,notes)
SELECT md5(s.id::text || n)::uuid,s.id,md5('saving request' || s.id::text || n)::uuid,n,
    CASE WHEN n % 5 = 0 THEN 'REMOVE' ELSE 'ADD' END,1000,date '2021-11-01' + n,''
FROM savings s CROSS JOIN generate_series(1,500) n;

INSERT INTO routine_plans(id,user_id,kind,recipient,name,amount,status,first_due_date,interval_months,total_cycles,initial_paid,notes,version)
SELECT md5('routine' || n)::uuid, u.id,'CONTRIBUTION','','Synthetic routine ' || n,1000,'ACTIVE','2021-11-01',1,0,0,'',1
FROM users u CROSS JOIN generate_series(1,30) n;
INSERT INTO routine_payments(id,plan_id,request_id,sequence,due_date)
SELECT md5(r.id::text || n)::uuid,r.id,md5('routine request' || r.id::text || n)::uuid,n,
    date '2021-11-01' + (n-1)*interval '1 month'
FROM routine_plans r CROSS JOIN generate_series(1,60) n;
INSERT INTO ledger_transactions(id,user_id,kind,category,description,amount,transaction_date,source_label,destination_label,notes,routine_payment_id)
SELECT md5('routine ledger' || p.id::text)::uuid,r.user_id,'expense','family',r.name,r.amount,p.due_date,'','','',p.id
FROM routine_payments p JOIN routine_plans r ON r.id=p.plan_id;

INSERT INTO billing_accounts(id,user_id,platform_id,platform_type,has_fixed_bill_date)
SELECT md5('bill account')::uuid,id,1,'PAY_LATER',false FROM users;
INSERT INTO billing_transactions(id,account_id,description,tenor,transaction_date,first_installment,transaction_kind,amount)
SELECT md5('bill' || n)::uuid, a.id, 'Synthetic bill ' || n,0,'2021-11-01','2021-11-01','SUBSCRIPTION',10000
FROM billing_accounts a CROSS JOIN generate_series(1,60) n;
INSERT INTO billing_installments(id,transaction_id,sequence,amount,due_date,charged_on,paid_at)
SELECT md5(b.id::text || n)::uuid,b.id,n,b.amount,d.due,d.due,
    CASE WHEN n <= 58 THEN d.due::timestamptz END
FROM billing_transactions b CROSS JOIN generate_series(1,60) n
CROSS JOIN LATERAL (SELECT date '2021-11-01' + (n-1)*interval '1 month' AS due) d;

INSERT INTO debts(id,user_id,kind,person_name,principal,transaction_date,due_date,interest_type,interest_rate)
SELECT md5('debt' || n)::uuid,u.id,'DEBT','Synthetic debt ' || n,100000,'2021-11-01','2026-10-31','NONE',0
FROM users u CROSS JOIN generate_series(1,20) n;
INSERT INTO debt_payments(id,debt_id,request_id,sequence,amount,payment_date)
SELECT md5(d.id::text || n)::uuid,d.id,md5('debt request' || d.id::text || n)::uuid,n,1000,date '2021-11-01' + (n-1)*interval '1 month'
FROM debts d CROSS JOIN generate_series(1,48) n;
"""


async def measure(client, label, path, repeats):
    elapsed = []
    for attempt in range(repeats + 2):
        start = perf_counter()
        response = await client.get(path)
        if attempt >= 2:
            elapsed.append((perf_counter() - start) * 1000)
        response.raise_for_status()
    payload = response.json()
    count = len(payload) if isinstance(payload, list) else payload['MonthTotals']['TransactionsCount']
    digest = hashlib.sha256(response.content).hexdigest()[:12]
    print(f'{label}: median={statistics.median(elapsed):.1f} ms, '
          f'range={min(elapsed):.1f}–{max(elapsed):.1f} ms, bytes={len(response.content)}, rows={count}, digest={digest}')
    return payload


async def run(repeats, scoped):
    schema = 'finance_reads_test_' + uuid4().hex
    async with engine.connect() as connection:
        db = (await connection.get_raw_connection()).driver_connection
        await db.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
        try:
            await db.execute((ROOT / 'database/000_init.sql').read_text(encoding='utf-8'))
            await db.execute(SEED_SQL)
            for table in ('ledger_transactions', 'saving_movements', 'billing_installments', 'routine_payments', 'debt_payments'):
                await db.execute(f'ANALYZE "{schema}".{table}')
            isolated = create_async_engine(
                engine.url, connect_args={**connect_args, 'server_settings': {'search_path': schema}},
            )
            try:
                sessions = async_sessionmaker(isolated, expire_on_commit=False)
                async def synthetic_db():
                    async with sessions() as session:
                        yield session

                app = FastAPI()
                app.include_router(routine_router)
                app.include_router(summary_router)
                app.dependency_overrides[get_db] = synthetic_db
                app.dependency_overrides[get_current_user] = lambda: User(id=OWNER)
                async with AsyncClient(transport=ASGITransport(app=app), base_url='http://benchmark') as client:
                    print(f'PostgreSQL {await db.fetchval("SHOW server_version_num")}, {repeats} runs each after 2 warmups, synthetic schema')
                    full = await measure(client, 'Transaksi semua bulan', '/transactions', repeats)
                    with patch('app.services.summary_service.local_today', return_value=AS_OF), patch(
                        'app.services.debt_service.local_today', return_value=AS_OF,
                    ):
                        await measure(client, 'Ringkasan', f'/summary?month={MONTH}', repeats)
                    if scoped:
                        monthly = await measure(client, 'Transaksi satu bulan', f'/transactions?month={MONTH}', repeats)
                        assert monthly == [row for row in full if row['TransactionDate'].startswith(MONTH)]
            finally:
                await isolated.dispose()
        finally:
            await db.execute(f'ROLLBACK; SET search_path TO public; DROP SCHEMA "{schema}" CASCADE')
    await engine.dispose()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=7, choices=range(1, 31), metavar='1-30')
    parser.add_argument('--scoped', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.repeats, args.scoped))
