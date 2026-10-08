import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4
import test_billing as fixture


class DebtInstallmentTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixture.BillingTests.asyncSetUp
    asyncTearDown=fixture.BillingTests.asyncTearDown
    auth_headers=fixture.BillingTests.auth_headers

    def body(self,**changes):
        return dict(Kind='RECEIVABLE',PersonName='Budi',Principal=1000001,TransactionDate='2026-01-31',DueDate='2026-02-28',InterestType='NONE',InstallmentCount=3)|changes

    async def create(self,**changes):
        return await self.client.post('/debts',headers=self.headers,json=self.body(**changes))

    async def test_schedule_month_anchor_rounding_range_and_validation(self):
        item=(await self.create(DueDate='2026-01-31')).json()
        self.assertEqual([b['DueDate'] for b in item['Installments']],['2026-01-31','2026-02-28','2026-03-31'])
        self.assertEqual([b['PrincipalAmount'] for b in item['Installments']],[333333,333333,333335])
        for kind in ['DEBT','RECEIVABLE']:
            result=await self.create(Kind=kind,InstallmentCount=60)
            self.assertEqual(result.status_code,201,result.text)
            self.assertEqual(len(result.json()['Installments']),60)
        for changes in [dict(InstallmentCount=61),dict(InstallmentCount=1.5),dict(InstallmentCount=2,DueDate=None),dict(Principal=1),dict(DueDate='9999-01-01'),dict(InstallmentAmounts=[1,2,3]),dict(InstallmentAmounts=[0,0,1000001]),dict(InstallmentCount=0,InstallmentAmounts=[1000001])]:
            self.assertEqual((await self.create(**changes)).status_code,422)

    async def test_source_ownership_and_snapshot_survives_bank_deletion(self):
        body=dict(PlatformId=1,AccountNumber='001234567890',CardNumber='0123456789012345',ValidThru='2029-07')
        bank=(await self.client.post('/bank-accounts',headers=self.headers,json=body)).json()
        source=bank['Id']
        result=await self.create(SourceBankAccountId=source)
        self.assertEqual(result.status_code,201,result.text)
        item=result.json();self.assertEqual(item['SourceBankName'],'BCA');self.assertEqual(item['SourceAccountNumberMasked'],'********7890')
        self.assertNotIn(body['AccountNumber'],result.text)
        self.assertEqual((await self.create(Kind='DEBT',SourceBankAccountId=source)).status_code,422)
        self.assertEqual((await self.client.post('/debts',headers=self.auth_headers(self.other_id),json=self.body(SourceBankAccountId=source))).status_code,422)
        self.assertEqual((await self.create(SourceBankAccountId=str(uuid4()))).status_code,422)
        self.assertEqual((await self.client.delete('/bank-accounts/'+source,headers=self.headers)).status_code,204)
        detail=(await self.client.get('/debts/'+item['Id'],headers=self.headers)).json()
        self.assertIsNone(detail['SourceBankAccountId']);self.assertEqual(detail['SourceBankName'],'BCA');self.assertEqual(detail['SourceAccountNumberMasked'],'********7890')
        edited=await self.client.patch('/debts/'+item['Id'],headers=self.headers,json=self.body(PersonName='Updated'))
        self.assertEqual(edited.json()['SourceBankName'],'BCA')

    async def test_override_payment_allocation_and_partial_lock(self):
        item=(await self.create(Principal=1000000,InstallmentCount=2)).json();path='/debts/'+item['Id']
        result=await self.client.patch(path+'/installments',headers=self.headers,json={'Amounts':[400000,600000]})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual([b['PrincipalAmount'] for b in result.json()['Installments']],[400000,600000])
        self.assertEqual((await self.client.patch(path+'/installments',headers=self.auth_headers(self.other_id),json={'Amounts':[400000,600000]})).status_code,404)
        self.assertEqual((await self.client.patch(path+'/installments',headers=self.headers,json={'Amounts':[1,1]})).status_code,422)
        paid=await self.client.post(path+'/payments',headers=self.headers,json={'RequestId':str(uuid4()),'Amount':100000,'PaymentDate':'2026-02-28'})
        self.assertEqual(paid.status_code,201,paid.text)
        self.assertEqual(paid.json()['Installments'][0]['PaidPrincipal'],100000)
        self.assertEqual((await self.client.patch(path+'/installments',headers=self.headers,json={'Amounts':[500000,500000]})).status_code,409)
        self.assertEqual((await self.client.patch(path,headers=self.headers,json=self.body(Principal=1000000,InstallmentCount=3))).status_code,409)

    async def test_interest_is_separate_from_principal_and_unpaid_rows_can_change(self):
        with patch('app.services.debt_service.local_today',return_value=date(2026,3,31)):
            item=(await self.create(Principal=1000000,DueDate='2026-02-28',InterestType='MONTHLY',InterestRate=2)).json();path='/debts/'+item['Id']
            paid=await self.client.post(path+'/payments',headers=self.headers,json={'RequestId':str(uuid4()),'Amount':353333,'PaymentDate':'2026-02-28'})
            self.assertEqual(paid.status_code,201,paid.text)
            item=paid.json();self.assertEqual(item['Payments'][0]['InterestPortion'],20000)
            self.assertEqual(item['Installments'][0]['PaidPrincipal'],333333)
            self.assertTrue(item['Installments'][0]['IsPaid'])
            edited=await self.client.patch(path+'/installments',headers=self.headers,json={'Amounts':[333333,300000,366667]})
            self.assertEqual(edited.status_code,200,edited.text)
            self.assertTrue(edited.json()['IsOverdue']) # The unpaid second bill was due March 28.
            self.assertEqual(edited.json()['RemainingPrincipal'],666667)
