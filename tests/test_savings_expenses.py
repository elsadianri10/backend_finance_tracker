"""Expense sources: isolated synthetic database, never application data."""
import unittest
from uuid import uuid4
from datetime import date, datetime, timezone
from unittest.mock import patch
from sqlalchemy import select
from app.models.billing_model import BillingAccount
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from app.models.routine_model import LedgerTransaction
import test_debt_savings as fixture


class SavingsExpenseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixture.DebtSavingsTests.asyncSetUp(self)
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 9, 5, 0, tzinfo=timezone.utc)
        clock = patch('app.services.billing_transaction_service.datetime', FixedDateTime)
        clock.start()
        self.addCleanup(clock.stop)
    asyncTearDown = fixture.DebtSavingsTests.asyncTearDown
    auth_headers = fixture.DebtSavingsTests.auth_headers
    new_saving = fixture.DebtSavingsTests.new_saving
    debt = fixture.DebtSavingsTests.debt
    get = fixture.DebtSavingsTests.get

    async def bill(self):
        async with self.sessions() as db:
            account = BillingAccount(user_id=self.user_id, platform_id=1, platform_type='PAY_LATER', has_fixed_bill_date=False, monthly_fee=0, payment_fee=0)
            db.add(account); await db.flush()
            item = BillingTransaction(account_id=account.id, description='Synthetic bill', tenor=3,
                transaction_kind='INSTALLMENT', transaction_date=date(2026,10,1), first_installment=date(2026,10,1), last_installment=date(2026,12,1), amount=500, notes='')
            db.add(item); await db.flush()
            bill = BillingInstallment(transaction_id=item.id, sequence=1, amount=500, due_date=date(2026,10,1))
            db.add(bill); await db.commit()
            return str(item.id), str(bill.id)

    async def plan(self, **changes):
        r = await self.client.post('/routine?month=2026-10', headers=self.headers, json={
            'Kind':'CONTRIBUTION','Recipient':'Synthetic','Name':'Expense','Amount':500,
            'FirstDueDate':'2026-10-09','TotalCycles':3} | changes)
        self.assertEqual(r.status_code,201,r.text)
        return r.json()['Id']

    def payment(self, **changes):
        return {'RequestId':str(uuid4()), 'Sequence':1,'Amount':500,'PaymentDate':'2026-10-09',
                'SourceBankId':self.banks[0], 'SavingId':self.saving} | changes

    async def test_plain_routine_retry_and_undo_reverse_savings(self):
        plan = await self.plan()
        path = '/routine/'+plan+'/payments?month=2026-10'
        body = self.payment()
        r = await self.client.post(path,headers=self.headers,json=body)
        self.assertEqual(r.status_code,201,r.text)
        self.assertTrue(r.json()['SavingUpdated'])
        self.assertEqual((await self.get('/savings/'+self.saving))['Balance'],2500)
        again = await self.client.post(path,headers=self.headers,json=body)
        self.assertEqual(again.json(),r.json())
        for delta in ({'SavingId':None},{'SourceBankId':self.banks[1]}):
            bad = await self.client.post(path,headers=self.headers,json=body|delta)
            self.assertEqual(bad.status_code,409,bad.text)
        payment = r.json()['Payments'][0]['Id']
        undone = await self.client.delete('/routine/'+plan+'/payments/'+payment+'?month=2026-10',headers=self.headers)
        self.assertEqual(undone.status_code,200,undone.text)
        self.assertTrue(undone.json()['SavingUpdated'])
        self.assertEqual((await self.get('/savings/'+self.saving))['Balance'],3000)
        self.assertEqual(await self.get('/transactions'),[])

    async def test_routine_linked_bill_and_debt_still_one_expense(self):
        bill, part = await self.bill()
        debt = await self.debt()
        for link, extra in [({'BillingTransactionId':bill},{'BillingInstallmentId':part}),({'DebtId':debt},{})]:
            plan = await self.plan(**link)
            path = '/routine/'+plan+'/payments?month=2026-10'
            body = self.payment(**extra)
            r = await self.client.post(path,headers=self.headers,json=body)
            self.assertEqual(r.status_code,201,r.text)
            self.assertTrue(r.json()['Payments'][0]['Transaction']['SavingMovementId'])
            self.assertEqual((await self.client.post(path,headers=self.headers,json=body)).status_code,201)
        self.assertEqual(len(await self.get('/transactions')),2)
        saved = await self.get('/savings/'+self.saving)
        self.assertEqual((saved['Balance'],len(saved['Movements'])),(2000,2))
        self.assertEqual((await self.get('/debts/'+debt))['RemainingAmount'],1500)

    async def test_direct_bill_success_and_insufficient_balance_rollback(self):
        bill, part = await self.bill()
        path = '/billing/transactions/'+bill+'/installments/'+part+'/pay'
        small = await self.new_saving(OpeningAmount=100)
        bad = await self.client.post(path,headers=self.headers,json={'SourceBankId':self.banks[0],'SavingId':small})
        self.assertEqual(bad.status_code,422,bad.text)
        self.assertIsNone((await self.get('/billing/transactions/'+bill))['Installments'][0]['PaidAt'])
        self.assertEqual(await self.get('/transactions'),[])
        r = await self.client.post(path,headers=self.headers,json={'SourceBankId':self.banks[0],'SavingId':self.saving})
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(r.json()['SavingUpdated'])
        self.assertEqual((await self.client.post(path,headers=self.headers,json={'SourceBankId':self.banks[0],'SavingId':self.saving})).status_code,409)
        self.assertEqual((await self.get('/savings/'+self.saving))['Balance'],2500)
        self.assertEqual(len(await self.get('/transactions')),1)

    async def test_stock_purchase_requires_expense_and_is_atomic_idempotent(self):
        n = await self.client.post('/stock-needs',headers=self.headers,json={'Name':'Synthetic','Category':'health','Subcategory':'vitamins'})
        need = n.json()['Id']
        p = await self.client.post('/stock-needs/'+need+'/products',headers=self.headers,json={'RequestId':str(uuid4()),'Brand':'Synthetic','ActiveCount':1,'ReserveCount':0})
        product = p.json()['Products'][0]
        path = '/stock-needs/'+need+'/products/'+product['Id']+'/purchases'
        body = {'RequestId':str(uuid4()),'Version':product['Version'],'Quantity':2,'PurchaseDate':'2026-10-09',
                'Amount':500,'RecordExpense':True,'SourceBankId':self.banks[0],'SavingId':self.saving}
        for delta in ({'RecordExpense':False},{'Amount':4000},{'SourceBankId':self.banks[1]}):
            bad = await self.client.post(path,headers=self.headers,json=body|delta)
            self.assertEqual(bad.status_code,422,bad.text)
            self.assertEqual((await self.get('/stock-needs'))[0]['Products'][0]['ReserveCount'],0)
            self.assertEqual(await self.get('/transactions'),[])
        r = await self.client.post(path,headers=self.headers,json=body)
        self.assertEqual(r.status_code,201,r.text)
        again = await self.client.post(path,headers=self.headers,json=body)
        self.assertEqual(again.status_code,201,again.text)
        self.assertEqual(again.json()['Products'][0]['ReserveCount'],2)
        rows = await self.get('/transactions')
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['SavingMovementId'])
        self.assertEqual((await self.get('/savings/'+self.saving))['Balance'],2500)
        bad = await self.client.post(path,headers=self.headers,json=body|{'SavingId':None})
        self.assertEqual(bad.status_code,409,bad.text)

    async def test_transaction_entry_bill_and_routine(self):
        bill, part = await self.bill()
        plan = await self.plan()
        for link in ({'BillingInstallmentId':part},{'RoutinePlanId':plan,'RoutineSequence':1}):
            body = {'RequestId':str(uuid4()),'Kind':'expense','Category':'bills','Description':'Synthetic',
                    'Amount':500,'TransactionDate':'2026-10-09','SourceBankId':self.banks[0],'SavingId':self.saving}|link
            r = await self.client.post('/transactions',headers=self.headers,json=body)
            self.assertEqual(r.status_code,201,r.text)
            self.assertTrue(r.json()['SavingMovementId'])
            self.assertEqual((await self.client.post('/transactions',headers=self.headers,json=body)).json(),r.json())
        self.assertEqual((await self.get('/savings/'+self.saving))['Balance'],2000)
        self.assertEqual(len(await self.get('/transactions')),2)

    async def test_routine_failures_and_transfer_source_rejection(self):
        plan = await self.plan()
        path = '/routine/'+plan+'/payments?month=2026-10'
        for body in (self.payment(Amount=4000),self.payment(SourceBankId=self.banks[1]),self.payment(SavingId=str(uuid4()))):
            bad = await self.client.post(path,headers=self.headers,json=body)
            self.assertIn(bad.status_code,(404,422),bad.text)
            self.assertEqual(await self.get('/transactions'),[])
            self.assertEqual((await self.get('/routine?month=2026-10'))[0]['CompletedCycles'],0)
        transfer = await self.plan(Kind='TRANSFER',DestinationBankId=self.banks[1])
        bad = await self.client.post('/routine/'+transfer+'/payments?month=2026-10',headers=self.headers,json=self.payment())
        self.assertEqual(bad.status_code,422,bad.text)
