import unittest
from uuid import uuid4
from sqlalchemy import select
import test_billing as fixture
from app.models import BillingAccount, BillingInstallment, BillingTransaction


class AccountManagementTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    card = fixture.BillingTests.card
    create = fixture.BillingTests.create

    async def account(self):
        response = await self.create(self.card())
        self.assertEqual(response.status_code, 201, response.text)
        self.account_id = response.json()['Id']
        self.path = '/billing/accounts/' + self.account_id
        return response.json()

    async def transaction(self):
        response = await self.client.post(self.path + '/transactions', headers=self.headers, json={'Description':'Laptop','Tenor':3,'FirstInstallment':'2028-01-17','LastInstallment':'2028-03-17','Amount':1500000})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def test_empty_account_can_be_deleted_by_owner_only(self):
        account = await self.account()
        self.assertTrue(account['CanDelete'])
        self.assertFalse(account['HasTransactions'])
        self.assertEqual((await self.client.delete(self.path, headers=self.auth_headers(self.other_id))).status_code, 404)
        self.assertEqual((await self.client.delete(self.path)).status_code, 401)
        deleted = await self.client.delete(self.path, headers=self.headers)
        self.assertEqual(deleted.status_code, 204, deleted.text)
        self.assertEqual(deleted.headers['cache-control'], 'no-store')
        self.assertEqual((await self.client.get(self.path, headers=self.headers)).status_code, 404)
        self.assertEqual((await self.client.get('/billing/accounts', headers=self.headers)).json(), [])

    async def test_deletion_requires_every_bill_paid_and_removes_children(self):
        await self.account()
        item = await self.transaction()
        other = await self.transaction()
        meta = (await self.client.get(self.path, headers=self.headers)).json()
        self.assertFalse(meta['CanDelete'])
        self.assertTrue(meta['HasTransactions'])
        self.assertEqual((await self.client.delete(self.path, headers=self.headers)).status_code,409)
        for transaction in (item,other):
            for bill in transaction['Installments']:
                meta = (await self.client.get(self.path, headers=self.headers)).json()
                self.assertFalse(meta['CanDelete'])
                response = await self.client.post(f"/billing/transactions/{transaction['Id']}/installments/{bill['Id']}/pay", headers=self.headers, json={})
                self.assertEqual(response.status_code,200,response.text)
        self.assertTrue((await self.client.get(self.path, headers=self.headers)).json()['CanDelete'])
        self.assertEqual((await self.client.delete(self.path, headers=self.headers)).status_code,204)
        async with self.sessions() as db:
            self.assertIsNone(await db.scalar(select(BillingTransaction)))
            self.assertIsNone(await db.scalar(select(BillingInstallment)))
            self.assertIsNone(await db.scalar(select(BillingAccount)))

    async def test_edit_keeps_encrypted_number_and_existing_schedule(self):
        original = await self.account()
        item = await self.transaction()
        async with self.sessions() as db:
            encrypted = (await db.scalar(select(BillingAccount))).account_number_encrypted
        body = self.card(AccountType='New label',ValidThru='2030-07',BillingDate=15,DueDate=19)
        del body['AccountNumber']
        self.assertEqual((await self.client.patch(self.path,headers=self.auth_headers(self.other_id),json=body)).status_code,404)
        response = await self.client.patch(self.path,headers=self.headers,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['AccountNumberMasked'],original['AccountNumberMasked'])
        self.assertNotIn('AccountNumber',response.json())
        async with self.sessions() as db:
            self.assertEqual((await db.scalar(select(BillingAccount))).account_number_encrypted,encrypted)
        unchanged = (await self.client.get('/billing/transactions/'+item['Id'],headers=self.headers)).json()
        self.assertEqual(unchanged['Installments'],item['Installments'])
        future = await self.transaction()
        self.assertEqual(future['Installments'][0]['DueDate'],'2028-01-19')
        unsupported = {'PlatformId':2,'PlatformType':'PAY_LATER','HasFixedBillDate':False}
        self.assertEqual((await self.client.patch(self.path,headers=self.headers,json=unsupported)).status_code,409)

    async def test_edit_replaces_number_encrypted_and_validates_conditional_fields(self):
        await self.account()
        result = await self.client.patch(self.path,headers=self.headers,json=self.card(AccountNumber='0012345678909999'))
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['AccountNumberMasked'],'************9999')
        self.assertNotIn('0012345678909999',result.text)
        body = {'PlatformId':2,'PlatformType':'PAY_LATER','HasFixedBillDate':False}
        self.assertEqual((await self.client.patch(self.path,headers=self.headers,json=body | {'AccountNumber':'0123456789012345'})).status_code,422)
        result = await self.client.patch(self.path,headers=self.headers,json=body)
        self.assertEqual(result.status_code,200,result.text)
        self.assertIsNone(result.json()['AccountNumberMasked'])
        card = self.card(); del card['AccountNumber']
        self.assertEqual((await self.client.patch(self.path,headers=self.headers,json=card)).status_code,422)
        self.assertEqual((await self.client.patch('/billing/accounts/'+str(uuid4()),headers=self.headers,json=card)).status_code,404)
