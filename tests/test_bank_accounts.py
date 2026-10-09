import os
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4
from sqlalchemy import select
import test_billing as fixture
from app.models import BillingPlatform
from app.models.bank_account_model import BankAccount
from app.helpers.bank_encryption import masked


class BankAccountTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    def body(self, **changes):
        return dict(PlatformId=1, AccountNumber='001234567890', CardNumber='0123456789012345', ValidThru='2029-07', AdminFee=15000, OthersFee=0) | changes

    async def create(self, **changes):
        return await self.client.post('/bank-accounts', headers=self.headers, json=self.body(**changes))

    async def test_providers_filter_banks_sort_and_billing_keeps_all(self):
        async with self.sessions() as db:
            db.add_all([BillingPlatform(id=4, name='AAA Paylater', bank_f=0), BillingPlatform(id=5, name='Bank Abjad', bank_f=1)])
            await db.commit()
        banks = await self.client.get('/bank-accounts/platforms', headers=self.headers)
        self.assertEqual([p['Name'] for p in banks.json()], ['Bank Abjad','BCA'])
        all_providers = await self.client.get('/billing/platforms',headers=self.headers)
        self.assertEqual([p['Name'] for p in all_providers.json()], ['Bank Abjad','BCA','AAA Paylater','GoPay Later'])
        for invalid in (2, 3, 999):
            result = await self.create(PlatformId=invalid)
            self.assertEqual(result.status_code,422)
            self.assertEqual(result.json()['detail'][0]['loc'],['body','PlatformId'])

    async def test_encrypted_owned_crud_and_edit_preserves_numbers(self):
        result=await self.create()
        self.assertEqual(result.status_code,201,result.text)
        account=result.json(); path='/bank-accounts/'+account['Id']
        self.assertEqual(account['AccountNumberMasked'],'********7890')
        self.assertEqual(account['CardNumberMasked'],'************2345')
        self.assertEqual(result.headers['cache-control'],'no-store')
        for number in (self.body()['AccountNumber'],self.body()['CardNumber']): self.assertNotIn(number,result.text)
        async with self.sessions() as db:
            row=await db.get(BankAccount,UUID(account['Id']))
            encrypted=row.account_number_encrypted
            self.assertNotIn(self.body()['AccountNumber'],encrypted)
            with self.assertRaises(Exception): masked(encrypted,row.id,row.user_id,'card')
            with self.assertRaises(Exception): masked(encrypted,row.id,self.other_id,'account')
        body=self.body(AdminFee=17000,ValidThru='2030-12');del body['AccountNumber'];del body['CardNumber']
        edited=await self.client.patch(path,headers=self.headers,json=body)
        self.assertEqual(edited.status_code,200,edited.text)
        self.assertEqual(edited.json()['AccountNumberMasked'],account['AccountNumberMasked'])
        self.assertEqual(edited.json()['AdminFee'],17000)
        async with self.sessions() as db:self.assertEqual((await db.get(BankAccount,UUID(account['Id']))).account_number_encrypted,encrypted)
        changed=await self.client.patch(path,headers=self.headers,json=self.body(AccountNumber='00000009999',CardNumber='0000000000007777'))
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertTrue(changed.json()['AccountNumberMasked'].endswith('9999'))
        other=self.auth_headers(self.other_id)
        for method in ['get','patch','delete']:
            kwargs={'json':body} if method=='patch' else {}
            self.assertEqual((await getattr(self.client,method)(path,headers=other,**kwargs)).status_code,404)
        self.assertEqual((await self.client.get('/bank-accounts',headers=other)).json(),[])
        self.assertEqual((await self.client.delete(path,headers=self.headers)).status_code,204)
        self.assertEqual((await self.client.get(path,headers=self.headers)).status_code,404)

    async def test_validation_does_not_echo_numbers_and_no_secrets(self):
        for changes in [dict(AccountNumber=12345678),dict(AccountNumber='1234'),dict(CardNumber='123'),dict(ValidThru='2029-13'),dict(AdminFee=-1),dict(OthersFee=1.5),dict(AdminFee='15000')]:
            result=await self.create(**changes)
            self.assertEqual(result.status_code,422,result.text)
            self.assertNotIn('input',result.json()['detail'][0])
        result=await self.create();path='/bank-accounts/'+result.json()['Id']
        self.assertEqual((await self.client.patch(path,headers=self.headers,json=self.body(AccountNumber=None))).status_code,422)
        self.assertEqual((await self.client.get('/bank-accounts')).status_code,401)
        with patch.dict(os.environ,{'ENCRYPTION_KEY':''}):
            self.assertEqual((await self.create()).status_code,503)
            self.assertEqual((await self.client.get(path,headers=self.headers)).status_code,503)
        self.assertEqual(len((await self.client.get('/bank-accounts',headers=self.headers)).json()),1)

    async def test_optional_card_fields_create_edit_and_clear(self):
        for mode in ('omitted', 'empty', 'null'):
            body = self.body()
            for key in ('CardNumber', 'ValidThru'):
                if mode == 'omitted':
                    del body[key]
                else:
                    body[key] = '' if mode == 'empty' else None
            result = await self.client.post('/bank-accounts', headers=self.headers, json=body)
            self.assertEqual(result.status_code, 201, result.text)
            self.assertEqual(result.json()['CardNumberMasked'], '')
            self.assertEqual(result.json()['ValidThru'], '')
            path = '/bank-accounts/' + result.json()['Id']
            added = await self.client.patch(path, headers=self.headers, json=self.body())
            self.assertEqual(added.status_code, 200, added.text)
            self.assertTrue(added.json()['CardNumberMasked'].endswith('2345'))
            edited = self.body(ValidThru='')
            del edited['CardNumber']
            preserved = await self.client.patch(path, headers=self.headers, json=edited)
            self.assertEqual(preserved.status_code, 200, preserved.text)
            self.assertEqual(preserved.json()['CardNumberMasked'], added.json()['CardNumberMasked'])
            cleared = await self.client.patch(path, headers=self.headers, json=self.body(CardNumber='', ValidThru=''))
            self.assertEqual(cleared.status_code, 200, cleared.text)
            self.assertEqual(cleared.json()['CardNumberMasked'], '')
            self.assertEqual(cleared.json()['ValidThru'], '')
            fetched = await self.client.get(path, headers=self.headers)
            self.assertEqual(fetched.json()['CardNumberMasked'], '')
