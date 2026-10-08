"""PostgreSQL concurrency check in a random schema; no application data touched."""
import asyncio
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv('.env')
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.config.db_config import engine as admin
from app.models import Base, User
from app.schemas.debt_schema import DebtCreate, PaymentCreate
from app.services import debt_service as service


async def check():
    schema = 'debt_test_' + uuid4().hex
    engine = create_async_engine(admin.url, connect_args={'server_settings': {'search_path': schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    created = False
    try:
        async with admin.begin() as db:
            await db.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        async with engine.begin() as db:
            await db.run_sync(Base.metadata.create_all)
        user_id = uuid4()
        async with sessions() as db:
            db.add(User(id=user_id,google_sub=uuid4().hex,email='synthetic@example.test',name='Synthetic',last_login_at=datetime.now(timezone.utc)))
            await db.commit()
        async def create():
            async with sessions() as db:
                return await service.create(DebtCreate(Kind='DEBT',PersonName='Synthetic',Principal=1000000,TransactionDate='2026-01-31'),user_id,db)
        async def pay(item, amount, request_id=None):
            async with sessions() as db:
                try:
                    result = await service.add_payment(item['Id'],PaymentCreate(RequestId=request_id or uuid4(),Amount=amount,PaymentDate='2026-03-31'),user_id,db)
                    return 201,result
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code,None
        with patch('app.services.debt_service.local_today',return_value=date(2026,3,31)):
            item = await create()
            results = await asyncio.gather(pay(item,600000),pay(item,600000))
            assert sorted(code for code,_ in results) == [201,422]
            async with sessions() as db:
                result = await service.detail(item['Id'],user_id,db)
                assert result['RemainingAmount'] == 400000 and len(result['Payments']) == 1
            item = await create()
            request_id = uuid4()
            results = await asyncio.gather(pay(item,400000,request_id),pay(item,400000,request_id))
            assert [code for code,_ in results] == [201,201]
            assert results[0][1]['Payments'][0]['Id'] == results[1][1]['Payments'][0]['Id']
            async with sessions() as db:
                result = await service.detail(item['Id'],user_id,db)
                assert len(result['Payments']) == 1 and result['RemainingAmount'] == 600000
            item = await create()
            async def delete():
                async with sessions() as db:
                    try:
                        await service.delete(item['Id'],user_id,db)
                        return 204
                    except HTTPException as error:
                        await db.rollback()
                        return error.status_code
            deleted,paid = await asyncio.gather(delete(),pay(item,100000))
            assert (deleted,paid[0]) in ((204,404),(409,201)),(deleted,paid[0])
            async with sessions() as db:
                item = await service.create(DebtCreate(Kind='RECEIVABLE',PersonName='Synthetic',Principal=1000000,TransactionDate='2026-01-31',InterestType='MONTHLY',InterestRate='2.00'),user_id,db)
                assert item['InterestAccrued'] == 40000
                item = await service.add_payment(item['Id'],PaymentCreate(RequestId=uuid4(),Amount=220000,PaymentDate='2026-02-28'),user_id,db)
                assert item['RemainingPrincipal'] == 800000 and item['RemainingInterest'] == 16000
        print('PASS: PostgreSQL exact monthly interest, concurrent overpayment protection, idempotent retries, delete/payment race. Synthetic schema only.')
    finally:
        await engine.dispose()
        if created:
            async with admin.begin() as db:
                await db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


if __name__ == '__main__':
    asyncio.run(check())
