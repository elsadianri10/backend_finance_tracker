"""Check 016 with synthetic PostgreSQL data; --apply upgrades configured DB without reset."""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
from app.config.db_config import engine
from app.models import Base
from app.schemas.routine_schema import RoutineInput, PaymentInput
from app.services import routine_service as service

NEW={'routine_plans','routine_payments','ledger_transactions','transaction_imports'}


async def check(apply=False):
    schema=None
    async with engine.connect() as connection:
        raw=(await connection.get_raw_connection()).driver_connection
        try:
            if not apply:
                schema='routine_migration_test_'+uuid4().hex
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET search_path TO "{schema}"'))
                baseline=(ROOT/'database/000_init.sql').read_text(encoding='utf-8')
                start=baseline.index('CREATE TABLE IF NOT EXISTS routine_plans')
                end=baseline.index('DO $$\nDECLARE required_column RECORD;',start)
                old=baseline[:start]+baseline[end:]
                old=old.replace("('routine_plans', 'version'),\n        ",'').replace("('ledger_transactions', 'kind'),\n        ",'')
                old=old.replace("('ledger_transactions', 'request_hash'),\n        ",'')
                old=old.replace("set_config('finance_tracker.reset', 'on', true)","set_config('finance_tracker.reset', 'off', true)")
                await raw.execute(old.replace('BEGIN;','').replace('COMMIT;',''))
                owner=uuid4()
                await connection.execute(text("INSERT INTO users(id,google_sub,email,name,last_login_at) VALUES(:id,'synthetic','synthetic@example.test','Synthetic',NOW())"),{'id':owner})
                await connection.execute(text("INSERT INTO split_bill_groups(id,user_id,name,start_date,end_date,version) VALUES(:id,:owner,'Synthetic existing','2026-10-01','2026-10-31',7)"),{'id':uuid4(),'owner':owner})
                await connection.commit()
            async with connection.begin():
                tables=sorted(name for name in Base.metadata.tables if name not in NEW)
                for table in tables:
                    await connection.execute(text(f'LOCK TABLE {table} IN SHARE MODE'))
                before={table:await raw.fetch(f'SELECT * FROM {table} ORDER BY 1,2') for table in tables}
                sql=(ROOT/'database/016_routines_transactions.sql').read_text(encoding='utf-8').replace('\nBEGIN;\n','\n',1).removesuffix('COMMIT;\n')
                await raw.execute(sql)
                after={table:await raw.fetch(f'SELECT * FROM {table} ORDER BY 1,2') for table in tables}
                assert before==after,'Existing data changed'
                for name in NEW:
                    assert await connection.scalar(text(f'SELECT count(*) FROM {name}'))==0
                assert not await connection.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name IN ('routine_plans','routine_payments','ledger_transactions','transaction_imports') AND data_type IN ('json','jsonb')"))
            print('PASS: 016 applied; all existing tables/records unchanged, four new relational tables empty, no JSON/JSONB.')
            if not apply:
                # Keep the 016 upgrade assertions independent; current ORM also needs 017.
                follow_up=(ROOT/'database/017_payment_sync.sql').read_text(encoding='utf-8').replace('BEGIN;','').replace('COMMIT;','')
                await raw.execute(follow_up)
                async with AsyncSession(bind=connection,expire_on_commit=False) as db:
                    plan=await service.save_plan(RoutineInput.model_validate({'Kind':'CONTRIBUTION','Recipient':'Family','Name':'Temporary assistance','Amount':200000,'FirstDueDate':'2026-10-31','TotalCycles':24,'InitialPaid':23}),owner,'2026-10',db)
                    from uuid import UUID
                    result=await service.pay(UUID(plan['Id']),PaymentInput.model_validate({'RequestId':str(uuid4()),'Sequence':24,'Amount':200000,'PaymentDate':'2026-10-09'}),owner,'2026-10',db)
                    assert result['Status']=='FINISHED'
                    assert (await service.list_transactions(owner,db))[0]['Amount']==200000
                    await db.rollback()
                    await service.undo(UUID(plan['Id']),UUID(result['Payments'][0]['Id']),owner,'2026-10',db)
                    assert await service.list_transactions(owner,db)==[]
                    await db.rollback()
                    result=await service.pay(UUID(plan['Id']),PaymentInput.model_validate({'RequestId':str(uuid4()),'Sequence':24,'Amount':200000,'PaymentDate':'2026-10-09'}),owner,'2026-10',db)
                    assert result['Status']=='FINISHED'
                print('PASS: PostgreSQL payment/ledger atomicity, completion, undo and re-payment partial unique indexes.')
        finally:
            await connection.rollback()
            if schema:
                await connection.execute(text('SET search_path TO public'))
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                await connection.commit()
    await engine.dispose()


if __name__=='__main__':asyncio.run(check('--apply' in sys.argv))
