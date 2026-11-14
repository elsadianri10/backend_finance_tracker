"""Reproduce the production FK error and verify ordered deletion in an isolated local PostgreSQL schema."""
import asyncio,sys
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from check_debt_installment_migration import engine
from test_split_bills import example,expense
from app.models import User,AccountAccess
from app.models.split_bill_model import SplitBillGroup,SplitBillParticipant,SplitBillExpense,SplitBillItem,SplitBillShare
from app.schemas.split_bill_schema import GroupCreate
from app.services import split_bill_service as service
MODELS=(SplitBillGroup,SplitBillParticipant,SplitBillExpense,SplitBillItem,SplitBillShare)
async def snapshot(db):
    return {model.__tablename__:[dict(row._mapping) for row in (await db.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns))).all()] for model in MODELS}
async def check():
    if engine.url.host not in {'localhost','127.0.0.1','::1'}:raise RuntimeError('This test only permits a loopback PostgreSQL database')
    schema='split_delete_test_'+uuid4().hex
    test_engine=None
    try:
        async with engine.connect() as conn:
            raw=(await conn.get_raw_connection()).driver_connection
            await raw.execute(f'CREATE SCHEMA "{schema}"; SET search_path TO "{schema}"')
            try:
                sql=(ROOT/'database/000_init.sql').read_text(encoding='utf-8').replace("set_config('finance_tracker.reset', 'on', true)","set_config('finance_tracker.reset', 'off', true)")
                await raw.execute(sql)
            finally:await raw.execute('SET search_path TO public')
        test_engine=create_async_engine(engine.url,connect_args={'server_settings':{'search_path':schema}})
        sessions=async_sessionmaker(test_engine,expire_on_commit=False)
        owner,other=uuid4(),uuid4()
        async with sessions() as db:
            for user_id,name in [(owner,'Owner'),(other,'Other')]:
                db.add(User(id=user_id,google_sub=str(user_id),email=name+'@example.test',name=name,last_login_at=datetime.now(timezone.utc)))
            await db.flush();db.add_all([AccountAccess(user_id=owner,complimentary=True),AccountAccess(user_id=other,complimentary=True)]);await db.commit()
            body=example(3);body['Expenses']=[expense(body),expense(body,20000)]
            target=await service.save(GroupCreate.model_validate(body),owner,db)
            protected=await service.save(GroupCreate.model_validate(body),other,db)
            before=await snapshot(db)
            # Same old implementation as deployed: DELETE only the parent group.
            await db.delete(await service.owned(target['Id'],owner,db,True))
            try:await db.commit()
            except IntegrityError as error:
                assert 'split_bill_participants' in str(error.orig) and 'split_bill_shares' in str(error.orig)
                await db.rollback()
            else:raise AssertionError('Old delete did not reproduce the production FK violation')
            assert before==await snapshot(db)
            print('PASS: reproduced original PostgreSQL FK violation; failed transaction preserved every group row.')
            try:await service.delete_group(target['Id'],other,db)
            except HTTPException as error:assert error.status_code==404
            else:raise AssertionError('Foreign owner was allowed to delete the group')
            assert before==await snapshot(db)
            # A commit failure after child DELETEs must roll back the full group.
            with patch.object(db,'commit',side_effect=RuntimeError('synthetic commit failure')):
                try:await service.delete_group(target['Id'],owner,db)
                except RuntimeError:await db.rollback()
                else:raise AssertionError('Commit failure was not raised')
            assert before==await snapshot(db)
            await service.delete_group(target['Id'],owner,db)
            after=await snapshot(db)
            for table,rows in before.items():
                expected=[row for row in rows if str(row['id'] if table=='split_bill_groups' else row['group_id'])!=str(target['Id'])]
                assert after[table]==expected,table
            assert await service.response(await service.owned(protected['Id'],other,db),db)==protected
            empty=example(2);empty['Expenses']=[]
            empty_group=await service.save(GroupCreate.model_validate(empty),owner,db)
            await service.delete_group(empty_group['Id'],owner,db)
            try:await service.delete_group(target['Id'],owner,db)
            except HTTPException as error:assert error.status_code==404
            else:raise AssertionError('Missing group should return 404')
            print('PASS: populated/empty group deletion, ownership, same client IDs across groups, atomic rollback, and other-group preservation.')
    finally:
        if test_engine:await test_engine.dispose()
        async with engine.connect() as conn:
            raw=(await conn.get_raw_connection()).driver_connection
            await raw.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await engine.dispose()
if __name__=='__main__':asyncio.run(check())
