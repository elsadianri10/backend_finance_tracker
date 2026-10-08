"""Optional PostgreSQL integration check: temporary schema, no real account data.

Run from the repository root: .venv/Scripts/python.exe tests/check_billing_postgres.py
"""
import asyncio
import sys
from datetime import date, datetime, timezone
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv('.env')
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.config.db_config import engine as admin_engine
from app.models import Base, User, BillingAccount, BillingPlatform
from app.schemas.billing_transaction_schema import TransactionCreate
from app.services import billing_transaction_service as service
from app.services import billing_service as accounts


async def check():
    schema = 'billing_test_' + uuid4().hex
    engine = create_async_engine(admin_engine.url, connect_args={'server_settings': {'search_path': schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    created = False
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        user_id, account_id = uuid4(), uuid4()
        async with sessions() as db:
            db.add_all([User(id=user_id, google_sub=uuid4().hex, email='synthetic@example.test', name='Synthetic', last_login_at=datetime.now(timezone.utc)), BillingPlatform(id=1,name='Synthetic')])
            await db.flush()
            db.add(BillingAccount(id=account_id,user_id=user_id,platform_id=1,platform_type='PAY_LATER',has_fixed_bill_date=False))
            await db.commit()
            item = await service.create(account_id, TransactionCreate(Description='Synthetic',Tenor=3,FirstInstallment='2028-01-31',LastInstallment='2028-03-31',Amount=1500000),user_id,db)
        async def pay():
            async with sessions() as db:
                try:
                    await service.mark_paid(item['Id'],item['Installments'][0]['Id'],user_id,db)
                    return 200
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code
        assert sorted(await asyncio.gather(pay(),pay())) == [200,409]
        async with sessions() as db:
            changed = await service.update_last(item['Id'],1499500,user_id,db)
            assert [bill['Amount'] for bill in changed['Installments']] == [1500000,1500000,1499500]
            assert [bill['DueDate'].isoformat() for bill in changed['Installments']] == ['2028-01-31','2028-02-29','2028-03-31']
            for bill in changed['Installments'][1:]:
                await service.mark_paid(item['Id'],bill['Id'],user_id,db)
        async def delete_account():
            async with sessions() as db:
                try:
                    await accounts.delete_account(account_id,user_id,db)
                    return 204
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code
        async def new_transaction():
            async with sessions() as db:
                try:
                    await service.create(account_id,TransactionCreate(Description='Concurrent',Tenor=3,FirstInstallment='2028-01-31',LastInstallment='2028-03-31',Amount=123),user_id,db)
                    return 201
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code
        outcome = tuple(await asyncio.gather(delete_account(),new_transaction()))
        assert outcome in ((204,404),(409,201)), outcome
        subscription_account = uuid4()
        async with sessions() as db:
            db.add(BillingAccount(id=subscription_account,user_id=user_id,platform_id=1,platform_type='PAY_LATER',has_fixed_bill_date=False))
            await db.commit()
            with patch('app.services.billing_transaction_service.local_today', return_value=date(2026,9,30)):
                subscription = await service.create(subscription_account, TransactionCreate(TransactionKind='SUBSCRIPTION',Description='Synthetic Subscription',FirstInstallment='2026-08-31',Amount=15000),user_id,db)
                assert len(subscription['Installments']) == 2
        async def subscription_detail():
            async with sessions() as db:
                return await service.detail(subscription['Id'],user_id,db)
        with patch('app.services.billing_transaction_service.local_today', return_value=date(2026,10,31)):
            left, right = await asyncio.gather(subscription_detail(), subscription_detail())
            assert len(left['Installments']) == len(right['Installments']) == 3
            assert [bill['Id'] for bill in left['Installments']] == [bill['Id'] for bill in right['Installments']]
            async with sessions() as db:
                changed = await service.update_subscription(subscription['Id'],20000,user_id,db)
                assert [bill['Amount'] for bill in changed['Installments']] == [15000] * 3
                stopped = await service.stop_subscription(subscription['Id'],user_id,db)
                assert stopped['NextChargeDate'] is None
        print('PASS: PostgreSQL locks, concurrent duplicate payment and subscription generation, exact amounts, month-end dates, future amount updates, stop. Synthetic schema cleaned up.')
    finally:
        await engine.dispose()
        if created:
            async with admin_engine.begin() as connection:
                # Only the random schema created above is removed; never a user schema.
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin_engine.dispose()


if __name__ == '__main__':
    asyncio.run(check())
