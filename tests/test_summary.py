import unittest
from datetime import date, datetime, timezone
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import select, func
import test_billing as fixture
import test_savings_sync as savings_fixture
import test_payment_sync as payment_fixture
from app.models.routine_model import LedgerTransaction
from app.models.billing_transaction_model import BillingInstallment, BillingTransaction
from app.models.billing_model import BillingAccount


class SummaryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    setup_saving = savings_fixture.SavingsSyncTests.setup_saving
    debt = payment_fixture.PaymentSyncTests.debt
    bill = payment_fixture.PaymentSyncTests.bill
    plan = payment_fixture.PaymentSyncTests.plan

    async def get(self, month='2026-10', headers=None):
        response = await self.client.get('/summary?month='+month, headers=headers or self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    async def test_monthly_flows_current_assets_links_and_ownership(self):
        banks, saving = await self.setup_saving()
        debt = await self.debt()
        receivable = await self.debt(kind='RECEIVABLE')
        await self.bill()
        plan = await self.plan()
        await self.plan(Name='Note', Status='NOTE', Amount=9999)
        for body in [
            dict(Kind='income',Category='salary',Amount=1000),
            dict(Kind='income',Category='receivable',Amount=100,DebtId=receivable['Id']),
            dict(Kind='expense',Category='debt',Amount=100,DebtId=debt['Id']),
            dict(Kind='expense',Category='family',Amount=250,RoutinePlanId=plan['Id'],RoutineSequence=1),
            dict(Kind='income',Category='cash_withdrawal',Amount=50,SavingId=saving,SourceBankId=banks[1]),
            dict(Kind='transfer',Category='savings',Amount=100,SavingId=saving,SourceBankId=banks[0],DestinationBankId=banks[1]),
        ]:
            response = await self.client.post('/transactions',headers=self.headers,json={
                'RequestId':str(uuid4()),'Description':'Synthetic summary','TransactionDate':'2026-10-09'}|body)
            self.assertEqual(response.status_code,201,response.text)
        async with self.sessions() as db:
            db.add(LedgerTransaction(user_id=self.user_id,kind='expense',category='other',description='Voided',amount=999,
                transaction_date=date(2026,10,9),source_label='',destination_label='',notes='',voided_at=datetime.now(timezone.utc)))
            await db.commit()
        result = await self.get()
        self.assertEqual(result['MonthTotals'], dict(Earnings=1000,Expenses=350,ReceivableReceived=100,NetCashflow=750,
            AllocationTransferred=100,CashWithdrawn=50,TransactionsCount=6))
        self.assertEqual(result['Savings']['CashBalance'],1050)
        self.assertEqual(result['Debts']['Owed'],900)
        self.assertEqual(result['Debts']['Receivable'],900)
        self.assertEqual(result['Routines']['Planned'],250)
        self.assertEqual(result['Routines']['Paid'],250)
        self.assertEqual(result['Routines']['Pending'],0)
        self.assertEqual(result['Routines']['NoteCount'],1)
        self.assertEqual(result['Bills']['PendingAmount'],500)
        self.assertEqual(result['Bills']['PendingCount'],1)
        earlier = await self.get('2026-09')
        self.assertEqual(earlier['MonthTotals']['TransactionsCount'],0)
        self.assertEqual(earlier['Savings']['CashBalance'],1050)
        other = await self.get(headers=self.auth_headers(self.other_id))
        self.assertEqual(other['Debts']['ActiveCount'],0)
        self.assertEqual(other['Savings']['CashBalance'],0)
        self.assertEqual(other['Banks']['Count'],0)
        self.assertEqual(other['Bills']['PendingCount'],0)
        self.assertEqual((await self.client.get('/summary?month=2026-13',headers=self.headers)).status_code,422)
        self.assertEqual((await self.client.get('/summary?month=2026-10')).status_code,401)

    async def test_accrued_subscription_summary_is_read_only(self):
        async with self.sessions() as db:
            account=BillingAccount(user_id=self.user_id,platform_id=1,platform_type='PAY_LATER',has_fixed_bill_date=False,monthly_fee=0,payment_fee=0)
            db.add(account); await db.flush()
            item=BillingTransaction(account_id=account.id,description='Synthetic subscription',tenor=0,
                transaction_kind='SUBSCRIPTION',transaction_date=date(2026,8,1),first_installment=date(2026,8,1),amount=100,notes='')
            db.add(item); await db.commit()
        with patch('app.services.summary_service.local_today',return_value=date(2026,10,9)):
            for _ in range(2):
                result=await self.get()
                self.assertEqual(result['Bills']['PendingAmount'],100)
                self.assertEqual(result['Bills']['OverdueAmount'],300)
                self.assertEqual(result['Bills']['OverdueCount'],3)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(BillingInstallment)),0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)),0)

    async def test_savings_types_prices_and_fees_are_not_cash_income(self):
        banks, saving = await self.setup_saving()
        for body in [
            dict(Kind='DEPOSIT',OpeningAmount=5000,BankAccountId=banks[0],MaturityDate='2027-10-01',InterestRate=5),
            dict(Kind='GOLD',MetalType='GOLD',WeightPerPiece=1.25,Pieces=2,PricePerGram=1000),
            dict(Kind='GOLD',MetalType='SILVER',WeightPerPiece=9.9,Pieces=1,PricePerGram=100),
            dict(Kind='GOLD',MetalType='GOLD',WeightPerPiece=1,Pieces=1),
        ]:
            response=await self.client.post('/savings',headers=self.headers,json={
                'Name':'Synthetic asset','StartDate':'2026-10-01'}|body)
            self.assertEqual(response.status_code,201,response.text)
        response=await self.client.patch('/bank-accounts/'+banks[0],headers=self.headers,json={'PlatformId':1,'AdminFee':10,'OthersFee':20})
        self.assertEqual(response.status_code,200,response.text)
        result=await self.get()
        self.assertEqual(result['Savings'],dict(CashBalance=1000,DepositBalance=5000,GoldGrams=3.5,SilverGrams=9.9,
            GoldValue=2500,SilverValue=990,UnpricedMetalsCount=1))
        self.assertEqual(result['Banks'],dict(Count=2,MonthlyFees=30))
        self.assertEqual(result['MonthTotals']['Earnings'],0)
        self.assertEqual(result['MonthTotals']['Expenses'],0)
