import unittest
from uuid import uuid4
import test_billing as fixture


class SavingsSyncTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def setup_saving(self):
        banks = []
        for number in ('0012345678', '0098765432'):
            result = await self.client.post('/bank-accounts', headers=self.headers, json={'PlatformId':1, 'AccountNumber':number})
            self.assertEqual(result.status_code,201,result.text)
            banks.append(result.json()['Id'])
        result = await self.client.post('/savings', headers=self.headers, json={'Kind':'CASH','Name':'BLU tabungan (sintetis)',
            'OpeningAmount':1000,'StartDate':'2026-10-01','BankAccountId':banks[1]})
        self.assertEqual(result.status_code,201,result.text)
        return banks, result.json()['Id']

    def payload(self, **changes):
        return {'RequestId':str(uuid4()), 'Kind':'income','Category':'cash_withdrawal','Description':'Tarik tunai',
            'Amount':250,'TransactionDate':'2026-10-09'} | changes

    async def saving(self, item_id):
        return (await self.client.get('/savings/'+item_id,headers=self.headers)).json()

    async def test_savings_origin_deposit_withdrawal_retries_and_atomic_failures(self):
        banks, saving = await self.setup_saving()
        path = '/savings/'+saving+'/movements'
        body = {'RequestId':str(uuid4()),'Direction':'ADD','Amount':500,'MovementDate':'2026-10-09',
            'RecordTransaction':True,'SourceBankId':banks[0],'Notes':'Setoran sintetis'}
        added = await self.client.post(path,headers=self.headers,json=body)
        self.assertEqual(added.status_code,201,added.text)
        self.assertEqual(added.json()['Balance'],1500)
        again = await self.client.post(path,headers=self.headers,json=body)
        self.assertEqual(again.status_code,201,again.text)
        self.assertEqual(len(again.json()['Movements']),1)
        rows = (await self.client.get('/transactions',headers=self.headers)).json()
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['Kind'],rows[0]['Category'],rows[0]['SourceBankId'],rows[0]['DestinationBankId']),
            ('transfer','savings',banks[0],banks[1]))
        self.assertEqual(rows[0]['TransactionDate'],'2026-10-09')
        self.assertEqual((await self.client.post(path,headers=self.headers,json=body|{'SourceBankId':banks[1]})).status_code,409)
        for source in (None, banks[1]):
            failed = await self.client.post(path,headers=self.headers,json=body|{'RequestId':str(uuid4()),'SourceBankId':source})
            self.assertEqual(failed.status_code,422,failed.text)
        missing_owner = await self.client.post(path,headers=self.auth_headers(self.other_id),json=body)
        self.assertEqual(missing_owner.status_code,404,missing_owner.text)
        withdrawal = body|{'RequestId':str(uuid4()),'Direction':'REMOVE','Amount':250,'SourceBankId':None}
        reduced = await self.client.post(path,headers=self.headers,json=withdrawal)
        self.assertEqual(reduced.status_code,201,reduced.text)
        self.assertEqual(reduced.json()['Balance'],1250)
        await self.client.post(path,headers=self.headers,json=withdrawal)
        rows = (await self.client.get('/transactions',headers=self.headers)).json()
        self.assertEqual(len(rows),2)
        cash = next(row for row in rows if row['Category']=='cash_withdrawal')
        self.assertEqual((cash['Kind'],cash['SourceBankId'],cash['DestinationBankId']),('income',banks[1],None))
        too_large = await self.client.post(path,headers=self.headers,json=withdrawal|{'RequestId':str(uuid4()),'Amount':1500})
        self.assertEqual(too_large.status_code,422,too_large.text)
        self.assertEqual((await self.saving(saving))['Balance'],1250)
        manual = withdrawal|{'RequestId':str(uuid4()),'Direction':'ADD','RecordTransaction':False}
        result = await self.client.post(path,headers=self.headers,json=manual)
        self.assertEqual(result.status_code,201,result.text)
        late = await self.client.post(path,headers=self.headers,json=manual|{'RecordTransaction':True,'SourceBankId':banks[0]})
        self.assertEqual(late.status_code,409,late.text)
        self.assertEqual(len((await self.client.get('/transactions',headers=self.headers)).json()),2)

    async def test_withdrawal_allocation_retry_and_validation_are_atomic(self):
        banks, saving = await self.setup_saving()
        payload = self.payload(SavingId=saving,SourceBankId=banks[1])
        result = await self.client.post('/transactions',headers=self.headers,json=payload)
        self.assertEqual(result.status_code,201,result.text)
        self.assertTrue(result.json()['SavingMovementId'])
        self.assertEqual((await self.saving(saving))['Balance'],750)
        again = await self.client.post('/transactions',headers=self.headers,json=payload)
        self.assertEqual(again.json(),result.json())
        self.assertEqual(len((await self.saving(saving))['Movements']),1)
        for invalid in (self.payload(SavingId=saving,SourceBankId=banks[0]), self.payload(SavingId=saving,SourceBankId=banks[1],Amount=1000),
                        self.payload(SavingId=saving,Kind='income',Category='salary')):
            bad = await self.client.post('/transactions',headers=self.headers,json=invalid)
            self.assertEqual(bad.status_code,422,bad.text)
        other = await self.client.post('/transactions',headers=self.auth_headers(self.other_id),json=self.payload(SavingId=saving))
        self.assertEqual(other.status_code,404,other.text)
        self.assertEqual(len((await self.client.get('/transactions',headers=self.headers)).json()),1)
        deposit = self.payload(SavingId=saving,Kind='transfer',Category='savings',SourceBankId=banks[0],DestinationBankId=banks[1],Amount=500)
        added = await self.client.post('/transactions',headers=self.headers,json=deposit)
        self.assertEqual(added.status_code,201,added.text)
        self.assertEqual((await self.saving(saving))['Balance'],1250)
        self.assertEqual((await self.client.delete('/transactions/'+added.json()['Id'],headers=self.headers)).status_code,409)
        self.assertEqual((await self.client.delete('/savings/'+saving,headers=self.headers)).status_code,409)

    async def test_routine_origin_transaction_undo_and_repay_share_movements(self):
        banks, saving = await self.setup_saving()
        result = await self.client.post('/routine?month=2026-10',headers=self.headers,json={
            'Kind':'TRANSFER','Recipient':'Saya','Name':'Alokasi','Amount':500,'FirstDueDate':'2026-10-09',
            'DestinationBankId':banks[1],'SavingId':saving})
        self.assertEqual(result.status_code,201,result.text)
        plan = result.json()
        payment = {'RequestId':str(uuid4()),'Sequence':1,'Amount':500,'PaymentDate':'2026-10-09','SourceBankId':banks[0]}
        path = '/routine/'+plan['Id']+'/payments?month=2026-10'
        paid = await self.client.post(path,headers=self.headers,json=payment)
        self.assertEqual(paid.status_code,201,paid.text)
        self.assertEqual((await self.saving(saving))['Balance'],1500)
        again = await self.client.post(path,headers=self.headers,json=payment)
        self.assertEqual(again.status_code,201,again.text)
        self.assertEqual(len((await self.saving(saving))['Movements']),1)
        payment_id = paid.json()['Payments'][0]['Id']
        undo = await self.client.delete('/routine/'+plan['Id']+'/payments/'+payment_id+'?month=2026-10',headers=self.headers)
        self.assertEqual(undo.status_code,200,undo.text)
        self.assertEqual((await self.saving(saving))['Balance'],1000)
        transfer = self.payload(Kind='transfer',Category='savings',SourceBankId=banks[0],DestinationBankId=banks[1],
            RoutinePlanId=plan['Id'],RoutineSequence=1,Amount=500)
        posted = await self.client.post('/transactions',headers=self.headers,json=transfer)
        self.assertEqual(posted.status_code,201,posted.text)
        self.assertEqual((await self.saving(saving))['Balance'],1500)
        self.assertEqual(len((await self.saving(saving))['Movements']),3)
        await self.client.post('/transactions',headers=self.headers,json=self.payload(SavingId=saving,SourceBankId=banks[1],Amount=1400))
        now = (await self.client.get('/routine?month=2026-10',headers=self.headers)).json()[0]
        failed = await self.client.delete('/routine/'+plan['Id']+'/payments/'+now['Payments'][0]['Id']+'?month=2026-10',headers=self.headers)
        self.assertEqual(failed.status_code,422,failed.text)
        self.assertEqual((await self.saving(saving))['Balance'],100)
        self.assertEqual(len((await self.client.get('/transactions',headers=self.headers)).json()),2)
