import unittest
from uuid import uuid4
from datetime import date, datetime, timezone
from unittest.mock import patch
from sqlalchemy import select, func
import test_billing as fixture
from app.models.billing_model import BillingAccount
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from app.models.routine_model import LedgerTransaction


class PaymentSyncTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def debt(self, kind='DEBT'):
        response = await self.client.post('/debts', headers=self.headers, json={
            'Kind': kind, 'PersonName': 'Synthetic', 'Principal': 1000,
            'TransactionDate': '2026-10-01', 'InterestType': 'NONE', 'InterestRate': 0})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def bill(self):
        async with self.sessions() as db:
            account = BillingAccount(user_id=self.user_id, platform_id=1, platform_type='PAY_LATER', has_fixed_bill_date=False, monthly_fee=0, payment_fee=0)
            db.add(account); await db.flush()
            item = BillingTransaction(account_id=account.id, description='Synthetic bill', tenor=3,
                transaction_kind='INSTALLMENT', transaction_date=date(2026,10,1), first_installment=date(2026,10,1), last_installment=date(2026,12,1), amount=500, notes='')
            db.add(item); await db.flush()
            bills = [BillingInstallment(transaction_id=item.id, sequence=i, amount=500, due_date=date(2026,9+i,1)) for i in (1,2,3)]
            db.add_all(bills); await db.commit()
            return str(item.id), [str(row.id) for row in bills]

    def transaction(self, **changes):
        return {'RequestId': str(uuid4()), 'Kind':'expense', 'Description':'Synthetic payment',
            'Category':'debt', 'Amount':250, 'TransactionDate':'2026-10-09', 'Notes':''} | changes

    async def rows(self):
        return (await self.client.get('/transactions', headers=self.headers)).json()

    async def plan(self, **changes):
        response=await self.client.post('/routine?month=2026-10',headers=self.headers,json={
            'Kind':'CONTRIBUTION','Recipient':'Synthetic','Name':'Payment','Amount':250,
            'FirstDueDate':'2026-10-09','TotalCycles':4} | changes)
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    async def test_transactions_debt_receivable_ownership_retry_and_rollback(self):
        debt=await self.debt()
        payload=self.transaction(DebtId=debt['Id'])
        result=await self.client.post('/transactions',headers=self.headers,json=payload)
        self.assertEqual(result.status_code,201,result.text)
        self.assertTrue(result.json()['DebtPaymentId'])
        again=await self.client.post('/transactions',headers=self.headers,json=payload)
        self.assertEqual(result.json(),again.json())
        current=(await self.client.get('/debts/'+debt['Id'],headers=self.headers)).json()
        self.assertEqual(current['RemainingAmount'],750)
        self.assertEqual(len(current['Payments']),1)
        self.assertEqual(len(await self.rows()),1)
        self.assertEqual((await self.client.post('/transactions',headers=self.headers,json=payload|{'Amount':300})).status_code,409)
        self.assertEqual((await self.client.post('/transactions',headers=self.auth_headers(self.other_id),json=self.transaction(DebtId=debt['Id']))).status_code,404)
        self.assertEqual((await self.client.post('/transactions',headers=self.headers,json=self.transaction(DebtId=debt['Id'],Amount=800))).status_code,422)
        self.assertEqual(len(await self.rows()),1)
        receivable=await self.debt('RECEIVABLE')
        receipt=await self.client.post('/transactions',headers=self.headers,json=self.transaction(DebtId=receivable['Id'],Kind='income',Category='receivable'))
        self.assertEqual(receipt.status_code,201,receipt.text)
        self.assertEqual(receipt.json()['Kind'],'income')
        self.assertEqual(receipt.json()['Category'],'receivable')
        self.assertEqual((await self.client.delete('/transactions/'+receipt.json()['Id'],headers=self.headers)).status_code,409)

    async def test_origin_debt_receipt_and_routine_share_one_ledger(self):
        debt=await self.debt()
        plan=await self.plan(DebtId=debt['Id'])
        payload={'RequestId':str(uuid4()),'Amount':250,'PaymentDate':'2026-10-09'}
        path='/debts/'+debt['Id']+'/payments'
        response=await self.client.post(path,headers=self.headers,json=payload)
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual((await self.client.post(path,headers=self.headers,json=payload)).status_code,201)
        rows=await self.rows()
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['RoutinePaymentId'])
        self.assertTrue(rows[0]['DebtPaymentId'])
        plans=(await self.client.get('/routine?month=2026-10',headers=self.headers)).json()
        self.assertEqual(plans[0]['CompletedCycles'],1)
        payment=await self.client.post('/routine/'+plan['Id']+'/payments?month=2026-10',headers=self.headers,
            json=payload|{'RequestId':str(uuid4()),'Sequence':2})
        self.assertEqual(payment.status_code,201,payment.text)
        self.assertEqual(len(await self.rows()),2)
        remaining=(await self.client.get('/debts/'+debt['Id'],headers=self.headers)).json()
        self.assertEqual(remaining['RemainingAmount'],500)
        receipt=await self.debt('RECEIVABLE')
        self.assertEqual((await self.client.post('/debts/'+receipt['Id']+'/payments',headers=self.headers,json=payload)).status_code,201)
        self.assertEqual((await self.rows())[0]['Kind'],'income')

    async def test_billing_origin_timestamp_and_routine_auto_progress(self):
        item,bills=await self.bill()
        plan=await self.plan(BillingTransactionId=item,Amount=500)
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026,10,9,18,30,tzinfo=timezone.utc)
        with patch('app.services.billing_transaction_service.datetime',FixedDateTime):
            response=await self.client.post('/billing/transactions/'+item+'/installments/'+bills[0]+'/pay',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        rows=await self.rows()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['TransactionDate'],'2026-10-10')
        self.assertTrue(rows[0]['RoutinePaymentId'])
        self.assertEqual(rows[0]['BillingInstallmentId'],bills[0])
        plans=(await self.client.get('/routine?month=2026-10',headers=self.headers)).json()
        self.assertEqual(plans[0]['CompletedCycles'],1)
        self.assertEqual((await self.client.post('/billing/transactions/'+item+'/installments/'+bills[0]+'/pay',headers=self.headers)).status_code,409)
        self.assertEqual(len(await self.rows()),1)

    async def test_transaction_billing_exact_amount_order_retry(self):
        item,bills=await self.bill()
        for target,amount in ((bills[1],500),(bills[0],499)):
            response=await self.client.post('/transactions',headers=self.headers,json=self.transaction(BillingInstallmentId=target,Amount=amount))
            self.assertIn(response.status_code,(409,422),response.text)
        self.assertEqual(await self.rows(),[])
        payload=self.transaction(BillingInstallmentId=bills[0],Amount=500)
        result=await self.client.post('/transactions',headers=self.headers,json=payload)
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual((await self.client.post('/transactions',headers=self.headers,json=payload)).json(),result.json())
        self.assertEqual(len(await self.rows()),1)
        current=(await self.client.get('/billing/transactions/'+item,headers=self.headers)).json()
        self.assertTrue(current['Installments'][0]['PaidAt'])
        self.assertIsNone(current['Installments'][1]['PaidAt'])

    async def test_transaction_routine_sequence_atomic_and_stale(self):
        plan=await self.plan()
        payload=self.transaction(RoutinePlanId=plan['Id'],RoutineSequence=1)
        response=await self.client.post('/transactions',headers=self.headers,json=payload)
        self.assertEqual(response.status_code,201,response.text)
        self.assertTrue(response.json()['RoutinePaymentId'])
        self.assertEqual((await self.client.post('/transactions',headers=self.headers,json=payload)).json(),response.json())
        self.assertEqual((await self.client.post('/transactions',headers=self.headers,json=payload|{'RequestId':str(uuid4())})).status_code,409)
        self.assertEqual(len(await self.rows()),1)

