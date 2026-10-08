import unittest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import test_billing as fixture
from app.services.billing_transaction_service import month_date


class BillingTransactionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    card = fixture.BillingTests.card
    create = fixture.BillingTests.create

    async def transaction(self, fixed=True, **changes):
        account = (await self.create(self.card(HasFixedBillDate=fixed, BillingDate=20 if fixed else None, DueDate=31 if fixed else None))).json()
        self.account_id = account['Id']
        body = {'Description': 'Laptop', 'Tenor': 3, 'FirstInstallment': '2028-01-31', 'LastInstallment': '2028-03-31', 'Amount': 1500000, 'Notes': 'Monthly'} | changes
        return await self.client.post(f"/billing/accounts/{self.account_id}/transactions", headers=self.headers, json=body)

    async def test_generation_ownership_and_persistence(self):
        for fixed in (True, False):
            result = await self.transaction(fixed)
            self.assertEqual(result.status_code, 201, result.text)
            self.assertEqual(result.headers['cache-control'], 'no-store')
            item = result.json()
            self.assertEqual([bill['DueDate'] for bill in item['Installments']], ['2028-01-31', '2028-02-29', '2028-03-31'])
            self.assertEqual([bill['Amount'] for bill in item['Installments']], [1500000] * 3)
            self.assertNotIn('AccountNumber', result.text)
            detail = f"/billing/transactions/{item['Id']}"
            self.assertEqual((await self.client.get(detail, headers=self.headers)).json(), item)
            self.assertEqual((await self.client.get(detail, headers=self.auth_headers(self.other_id))).status_code, 404)
            self.assertEqual((await self.client.get(f"/billing/accounts/{self.account_id}/transactions", headers=self.headers)).json(), [item])
            self.assertEqual((await self.client.get(f"/billing/accounts/{self.account_id}/transactions", headers=self.auth_headers(self.other_id))).status_code, 404)

    async def test_payment_is_sequential_and_irreversible(self):
        item = (await self.transaction()).json()
        base = f"/billing/transactions/{item['Id']}"
        bills = item['Installments']
        async def pay(index, headers=None):
            return await self.client.post(f"{base}/installments/{bills[index]['Id']}/pay", headers=headers or self.headers, json={})
        self.assertEqual((await pay(1)).status_code, 409)
        self.assertEqual((await pay(0, self.auth_headers(self.other_id))).status_code, 404)
        first = await pay(0)
        self.assertEqual(first.status_code, 200)
        self.assertIsNotNone(first.json()['Installments'][0]['PaidAt'])
        self.assertEqual((await pay(0)).status_code, 409)
        self.assertEqual((await pay(2)).status_code, 409)
        self.assertEqual((await pay(1)).status_code, 200)
        self.assertEqual((await pay(2)).status_code, 200)
        self.assertEqual((await pay(2)).status_code, 409)
        self.assertEqual((await self.client.patch(f"{base}/installments/{bills[0]['Id']}/pay", headers=self.headers, json={'PaidAt':None})).status_code, 405)

    async def test_last_amount_only_until_paid(self):
        item = (await self.transaction()).json()
        base = f"/billing/transactions/{item['Id']}"
        result = await self.client.patch(base + '/last-amount', headers=self.headers, json={'Amount':1499500})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual([bill['Amount'] for bill in result.json()['Installments']], [1500000,1500000,1499500])
        self.assertEqual((await self.client.patch(base + '/last-amount', headers=self.auth_headers(self.other_id), json={'Amount':1})).status_code, 404)
        for bill in item['Installments']:
            self.assertEqual((await self.client.post(f"{base}/installments/{bill['Id']}/pay", headers=self.headers, json={})).status_code, 200)
        self.assertEqual((await self.client.patch(base + '/last-amount', headers=self.headers, json={'Amount':123})).status_code, 409)

    async def test_validation_and_zero_tenor(self):
        for change in ({'Tenor':2}, {'Tenor':False}, {'Amount':0}, {'Amount':1.5}, {'Amount':True}, {'Description':'  '}, {'LastInstallment':'2028-04-01'}):
            response = await self.transaction(**change)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn('input', response.text)
        today = datetime.now(timezone(timedelta(hours=7))).date()
        first = month_date(today, 1, 31).isoformat()
        result = await self.transaction(Tenor=0, FirstInstallment=first, LastInstallment=first)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(len(result.json()['Installments']), 1)
        self.assertEqual(result.json()['Installments'][0]['Amount'],1500000)
        response = await self.transaction(Tenor=0, FirstInstallment='2028-01-01', LastInstallment='2028-01-01')
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['FirstInstallment'], '2028-01-01')
        self.assertEqual(response.json()['LastInstallment'], '2028-01-01')
        self.assertEqual((await self.client.get(f'/billing/transactions/{uuid4()}')).status_code,401)

    async def test_manual_first_date_and_fixed_due_date_are_separate(self):
        result = await self.transaction(FirstInstallment='2028-01-17', LastInstallment='2028-03-17')
        self.assertEqual(result.status_code, 201, result.text)
        item = result.json()
        self.assertEqual(item['FirstInstallment'], '2028-01-17')
        self.assertEqual(item['LastInstallment'], '2028-03-17')
        self.assertEqual([bill['DueDate'] for bill in item['Installments']], ['2028-01-31','2028-02-29','2028-03-31'])
