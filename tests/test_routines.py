import unittest
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import select, func
import test_billing as fixture
from app.models.routine_model import LedgerTransaction, RoutinePayment


class RoutineTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    def plan(self, **changes):
        return {'Kind':'CONTRIBUTION','Recipient':'Orang Tua','Name':'Rutin','Amount':900000,'Status':'ACTIVE',
                'FirstDueDate':'2026-10-31','IntervalMonths':1,'TotalCycles':0,'InitialPaid':0,'Notes':''} | changes

    async def create(self, **changes):
        result = await self.client.post('/routine?month=2026-10', headers=self.headers, json=self.plan(**changes))
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    async def pay(self, plan, **changes):
        return await self.client.post('/routine/'+plan['Id']+'/payments?month=2026-10',headers=self.headers,
                json={'RequestId':str(uuid4()),'Sequence':plan['NextSequence'],'Amount':plan['Amount'],'PaymentDate':'2026-10-09','Notes':''}|changes)

    async def test_note_schedule_components_and_completion(self):
        note = await self.create(Kind='SUBSCRIPTION',Recipient='',Name='Apple Music',Status='NOTE',Amount=0)
        self.assertEqual(note['PlannedAmount'],0)
        self.assertEqual((await self.pay(note)).status_code,422)
        self.assertEqual((await self.pay(note,Amount=55000)).status_code,409)
        routine = await self.create()
        help_plan = await self.create(Name='Bantuan elektronik',Amount=120000,TotalCycles=12,InitialPaid=11)
        self.assertEqual(routine['PlannedAmount']+help_plan['PlannedAmount'],1020000)
        paid=await self.pay(help_plan)
        self.assertEqual(paid.status_code,201,paid.text)
        result=paid.json()
        self.assertEqual(result['CompletedCycles'],12)
        self.assertEqual(result['Status'],'FINISHED')
        self.assertIsNone(result['NextSequence'])
        later=await self.client.get('/routine?month=2026-11',headers=self.headers)
        self.assertEqual(sum(row['PlannedAmount'] for row in later.json()),900000)
        ledger=(await self.client.get('/transactions',headers=self.headers)).json()
        self.assertEqual(len(ledger),1)
        self.assertEqual(ledger[0]['Amount'],120000)
        self.assertEqual(ledger[0]['Kind'],'expense')
        self.assertEqual((await self.client.delete('/transactions/'+ledger[0]['Id'],headers=self.headers)).status_code,409)
        self.assertEqual((await self.client.delete('/routine/'+help_plan['Id'],headers=self.headers)).status_code,409)
        undo=await self.client.delete('/routine/'+help_plan['Id']+'/payments/'+result['Payments'][0]['Id']+'?month=2026-10',headers=self.headers)
        self.assertEqual(undo.status_code,200,undo.text)
        self.assertEqual(undo.json()['Status'],'ACTIVE')
        self.assertEqual((await self.client.get('/transactions',headers=self.headers)).json(),[])
        repaid=await self.pay(undo.json())
        self.assertEqual(repaid.status_code,201,repaid.text)

    async def test_payment_retry_month_end_and_order(self):
        plan=await self.create(TotalCycles=5)
        request=str(uuid4())
        first=await self.pay(plan,RequestId=request)
        again=await self.pay(plan,RequestId=request)
        self.assertEqual(first.json(),again.json())
        self.assertEqual((await self.pay(plan,RequestId=request,Amount=1)).status_code,409)
        self.assertEqual((await self.pay(plan)).status_code,409)
        self.assertEqual(first.json()['NextDueDate'],'2026-11-30')
        second=await self.pay(first.json())
        result=second.json()
        self.assertEqual(result['NextDueDate'],'2026-12-31')
        old=result['Payments'][0]['Id']
        self.assertEqual((await self.client.delete('/routine/'+plan['Id']+'/payments/'+old+'?month=2026-10',headers=self.headers)).status_code,409)
        body=self.plan(TotalCycles=5,Version=result['Version'],FirstDueDate='2026-10-01')
        self.assertEqual((await self.client.patch('/routine/'+plan['Id']+'?month=2026-10',headers=self.headers,json=body)).status_code,422)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)),2)

    async def banks(self):
        ids=[]
        for value in ('12345678','23456789'):
            response=await self.client.post('/bank-accounts',headers=self.headers,json={'PlatformId':1,'AccountNumber':value,'CardNumber':'1234567812345678','ValidThru':'2029-07','AdminFee':0,'OthersFee':0})
            self.assertEqual(response.status_code,201,response.text)
            ids.append(response.json()['Id'])
        return ids

    async def test_transfer_ownership_crud_and_validation(self):
        source,destination=await self.banks()
        plan=await self.create(Kind='TRANSFER',Recipient='Tabungan BLU',Amount=5000000,DestinationBankId=destination)
        self.assertEqual((await self.pay(plan,SourceBankId=destination)).status_code,422)
        response=await self.pay(plan,SourceBankId=source)
        self.assertEqual(response.status_code,201,response.text)
        ledger=(await self.client.get('/transactions',headers=self.headers)).json()[0]
        self.assertEqual(ledger['Kind'],'transfer')
        self.assertNotIn('12345678',ledger['SourceLabel'])
        self.assertEqual((await self.client.get('/routine?month=2026-10',headers=self.auth_headers(self.other_id))).json(),[])
        self.assertEqual((await self.client.post('/routine/'+plan['Id']+'/payments?month=2026-10',headers=self.auth_headers(self.other_id),json={'RequestId':str(uuid4()),'Sequence':1,'Amount':1,'PaymentDate':'2026-10-09'})).status_code,404)
        self.assertEqual((await self.client.post('/routine?month=2026-10',headers=self.auth_headers(self.other_id),json=self.plan(Kind='TRANSFER',DestinationBankId=source))).status_code,404)
        manual={'Kind':'income','Description':'Gaji','Category':'salary','Amount':12000000,'TransactionDate':'2026-10-01','DestinationBankId':source}
        created=await self.client.post('/transactions',headers=self.headers,json=manual)
        self.assertEqual(created.status_code,201,created.text)
        path='/transactions/'+created.json()['Id']
        self.assertEqual((await self.client.patch(path,headers=self.auth_headers(self.other_id),json=manual)).status_code,404)
        updated=await self.client.patch(path,headers=self.headers,json=manual|{'Amount':13000000,'Category':'top_up'})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()['Category'],'top_up')
        self.assertEqual((await self.client.delete(path,headers=self.headers)).status_code,204)
        self.assertEqual((await self.client.get('/transactions')).status_code,401)
        self.assertEqual((await self.client.get('/routine?month=2026-13',headers=self.headers)).status_code,422)
        for value in (True,1.5,-1):
            self.assertEqual((await self.client.post('/transactions',headers=self.headers,json=manual|{'Amount':value})).status_code,422)

    async def test_import_once_no_resurrection(self):
        old={'id':'old-browser-id','type':'expense','description':'Internet','category':'bills','amount':277500,'date':'2026-10-09'}
        payload={'Transactions':[old]}
        for _ in range(2):
            self.assertEqual((await self.client.post('/transactions/import',headers=self.headers,json=payload)).status_code,200)
        rows=(await self.client.get('/transactions',headers=self.headers)).json()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['Amount'],277500)
        await self.client.delete('/transactions/'+rows[0]['Id'],headers=self.headers)
        await self.client.post('/transactions/import',headers=self.headers,json=payload)
        self.assertEqual((await self.client.get('/transactions',headers=self.headers)).json(),[])

    async def test_billing_link_marks_paid_and_prevents_duplicate(self):
        from app.models.billing_model import BillingAccount
        from app.models.billing_transaction_model import BillingTransaction,BillingInstallment
        from datetime import date
        async with self.sessions() as db:
            account=BillingAccount(user_id=self.user_id,platform_id=1,platform_type='PAY_LATER',has_fixed_bill_date=False,monthly_fee=0,payment_fee=0)
            db.add(account);await db.flush()
            bill=BillingTransaction(account_id=account.id,description='Internet',tenor=0,transaction_kind='SUBSCRIPTION',transaction_date=date(2026,10,1),first_installment=date(2026,10,1),amount=277500,notes='')
            db.add(bill);await db.flush()
            installment=BillingInstallment(transaction_id=bill.id,sequence=1,amount=277500,due_date=date(2026,10,9))
            db.add(installment);await db.commit()
            bill_id,installment_id=bill.id,installment.id
        plan=await self.create(Kind='SUBSCRIPTION',Recipient='',Amount=277500,BillingTransactionId=str(bill_id))
        paid=await self.pay(plan,BillingInstallmentId=str(installment_id))
        self.assertEqual(paid.status_code,201,paid.text)
        async with self.sessions() as db:
            self.assertIsNotNone((await db.get(BillingInstallment,installment_id)).paid_at)
        self.assertEqual((await self.pay(paid.json(),BillingInstallmentId=str(installment_id))).status_code,409)
        choices=(await self.client.get('/routine/options',headers=self.headers)).json()
        self.assertEqual(choices['Bills'][0]['PaidInstallments'],[])
