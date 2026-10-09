"""Full API preview with synthetic data in memory; never connects to the app DB."""
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['SECRET_KEY']='synthetic-routine-preview-secret-'+'x'*40
os.environ['ENCRYPTION_KEY']='ab'*32
import jwt
import uvicorn
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from main import app
from app.config.db_config import get_db
from app.config import auth_settings as settings
from app.models import Base,User,BillingPlatform
from app.schemas.bank_account_schema import BankAccountCreate
from app.schemas.routine_schema import RoutineInput,TransactionInput
from app.services import bank_account_service as banks, routine_service as service
from app.schemas.debt_schema import DebtCreate
from app.services import debt_service
from app.services import savings_service
from app.schemas.savings_schema import SavingCreate
from app.models.billing_model import BillingAccount
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from datetime import date

engine=create_async_engine('sqlite+aiosqlite:///:memory:')
@event.listens_for(engine.sync_engine,'connect')
def fk(connection,record):connection.execute('PRAGMA foreign_keys=ON')
sessions=async_sessionmaker(engine,expire_on_commit=False)
owner=uuid4()
now=datetime.now(timezone.utc)
token=jwt.encode({'sub':str(owner),'iat':now,'exp':now+timedelta(hours=2),'type':'access','iss':settings.TOKEN_ISSUER,'aud':settings.TOKEN_AUDIENCE},settings.SECRET_KEY,algorithm='HS256')

async def preview_db():
    async with sessions() as db:yield db
app.dependency_overrides[get_db]=preview_db

@app.get('/__ready')
async def ready():return {'Token':token}

@asynccontextmanager
async def lifespan(application):
    async with engine.begin() as connection:await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        db.add(User(id=owner,google_sub='preview',email='preview@example.test',name='Preview Rutin',last_login_at=now))
        db.add_all([BillingPlatform(id=1,name='BCA',bank_f=1),BillingPlatform(id=2,name='BLU',bank_f=1)])
        await db.commit()
        account_ids=[]
        for platform,number in ((1,'12345678'),(2,'23456789')):
            bank=await banks.create(BankAccountCreate.model_validate({'PlatformId':platform,'AccountNumber':number,'CardNumber':'1234567812345678','ValidThru':'2029-07','AdminFee':0,'OthersFee':0}),owner,db)
            account_ids.append(bank['Id'])
        month=datetime.now().strftime('%Y-%m')
        saving = await savings_service.create(SavingCreate(Kind='CASH',Name='Tabungan BLU (contoh)',OpeningAmount=1000000,
            StartDate=month+'-01',BankAccountId=account_ids[1]),owner,db)
        for kind,name,amount in (('DEBT','Hutang elektronik (contoh)',600000),('RECEIVABLE','Piutang teman (contoh)',300000)):
            await debt_service.create(DebtCreate(Kind=kind,PersonName=name,Principal=amount,TransactionDate=date.fromisoformat(month+'-01')),owner,db)
        account=BillingAccount(user_id=owner,platform_id=1,platform_type='PAY_LATER',has_fixed_bill_date=False,monthly_fee=0,payment_fee=0)
        db.add(account);await db.flush()
        bill=BillingTransaction(account_id=account.id,description='Cicilan elektronik (contoh)',tenor=3,transaction_kind='INSTALLMENT',transaction_date=date.fromisoformat(month+'-01'),first_installment=date.fromisoformat(month+'-01'),last_installment=service.add_months(date.fromisoformat(month+'-01'),2),amount=150000,notes='')
        db.add(bill);await db.flush()
        db.add_all([BillingInstallment(transaction_id=bill.id,sequence=index+1,amount=150000,due_date=service.add_months(date.fromisoformat(month+'-01'),index)) for index in range(3)])
        await db.commit()
        base={'Kind':'SUBSCRIPTION','Recipient':'','FirstDueDate':month+'-09','IntervalMonths':1,'TotalCycles':0,'InitialPaid':0,'Status':'ACTIVE'}
        for values in ({'Name':'Internet (Biznet)','Amount':277500},{'Name':'Pulsa 2 Nomor (XL)','Amount':25000},{'Name':'YouTube Premium','Amount':25715},{'Name':'XL Prioritas','Amount':77700,'Status':'NOTE'},{'Name':'Apple Music','Amount':55000,'Status':'NOTE'},
                       {'Kind':'CONTRIBUTION','Recipient':'Orang Tua','Name':'Setoran rutin','Amount':900000},
                       {'Kind':'CONTRIBUTION','Recipient':'Orang Tua','Name':'Bantuan elektronik','Amount':120000,'TotalCycles':12,'InitialPaid':7},
                       {'Kind':'CONTRIBUTION','Recipient':'Adik','Name':'Bantuan pembayaran','Amount':200000,'TotalCycles':24,'InitialPaid':17},
                       {'Kind':'TRANSFER','Recipient':'Tabungan BLU','Name':'Alokasi bulanan','Amount':5000000,'DestinationBankId':str(account_ids[1]),'SavingId':str(saving['Id'])}):
            await service.save_plan(RoutineInput.model_validate(base|values),owner,month,db)
        await service.save_transaction(TransactionInput.model_validate({'Kind':'income','Description':'Gaji bulanan (contoh)','Category':'salary','Amount':12000000,'TransactionDate':month+'-01','DestinationBankId':str(account_ids[0])}),owner,db)
    yield
    await engine.dispose()
app.router.lifespan_context=lifespan
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=int(sys.argv[1]),log_level='warning')
