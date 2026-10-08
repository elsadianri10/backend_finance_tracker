import unittest
from datetime import date
from unittest.mock import patch

import test_billing as fixture


class SubscriptionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    card = fixture.BillingTests.card
    create = fixture.BillingTests.create

    async def subscription(self, fixed=True, first='2026-08-31', **changes):
        account = await self.create(self.card(HasFixedBillDate=fixed, BillingDate=3 if fixed else None, DueDate=19 if fixed else None))
        self.account_path = '/billing/accounts/' + account.json()['Id']
        body = {'TransactionKind': 'SUBSCRIPTION', 'Description': 'Apple Storage', 'FirstInstallment': first, 'Amount': 15000} | changes
        result = await self.client.post(self.account_path + '/transactions', headers=self.headers, json=body)
        self.assertEqual(result.status_code, 201, result.text)
        self.path = '/billing/transactions/' + result.json()['Id']
        return result.json()

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 7))
    async def test_generation_is_idempotent_and_fixed_period_is_correct(self, _):
        item = await self.subscription()
        self.assertIsNone(item['LastInstallment'])
        self.assertEqual([bill['ChargedOn'] for bill in item['Installments']], ['2026-08-31', '2026-09-30'])
        self.assertEqual([bill['DueDate'] for bill in item['Installments']], ['2026-09-19', '2026-10-19'])
        self.assertEqual(item['NextChargeDate'], '2026-10-31')
        self.assertEqual(item['NextDueDate'], '2026-11-19')
        for _ in range(2):
            detail = await self.client.get(self.path, headers=self.headers)
            self.assertEqual(detail.json(), item)
            listed = await self.client.get(self.account_path + '/transactions', headers=self.headers)
            self.assertEqual(listed.json(), [item])
        with patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 11, 30)):
            detail = await self.client.get(self.path, headers=self.headers)
            self.assertEqual(len(detail.json()['Installments']), 4)
            self.assertEqual(detail.json()['Installments'][-1]['ChargedOn'], '2026-11-30')

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 7))
    async def test_future_amount_preserves_issued_bills_and_date_snapshot(self, _):
        await self.subscription()
        changed = await self.client.patch(self.path + '/subscription-amount', headers=self.headers, json={'Amount': 20000})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual([bill['Amount'] for bill in changed.json()['Installments']], [15000, 15000])
        updated_account = await self.client.patch(self.account_path, headers=self.headers, json=self.card(BillingDate=20, DueDate=5, AccountNumber=None))
        self.assertEqual(updated_account.status_code, 200, updated_account.text)
        with patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 31)):
            detail = (await self.client.get(self.path, headers=self.headers)).json()
            self.assertEqual([bill['Amount'] for bill in detail['Installments']], [15000, 15000, 20000])
            self.assertEqual(detail['Installments'][-1]['DueDate'], '2026-11-19')

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 7))
    async def test_stop_preserves_debt_and_sequential_payments(self, _):
        item = await self.subscription()
        self.assertEqual((await self.client.delete(self.account_path, headers=self.headers)).status_code, 409)
        self.assertEqual((await self.client.post(self.path + '/stop', headers=self.auth_headers(self.other_id), json={})).status_code, 404)
        self.assertEqual((await self.client.post(self.path + '/stop', json={})).status_code, 401)
        stopped = await self.client.post(self.path + '/stop', headers=self.headers, json={})
        self.assertEqual(stopped.status_code, 200, stopped.text)
        self.assertEqual(stopped.json()['StoppedOn'], '2026-10-07')
        self.assertIsNone(stopped.json()['NextChargeDate'])
        self.assertEqual(stopped.json()['Installments'], item['Installments'])
        self.assertEqual((await self.client.post(self.path + '/stop', headers=self.headers, json={})).json(), stopped.json())
        with patch('app.services.billing_transaction_service.local_today', return_value=date(2027, 1, 1)):
            self.assertEqual(len((await self.client.get(self.path, headers=self.headers)).json()['Installments']), 2)
        self.assertEqual((await self.client.patch(self.path + '/subscription-amount', headers=self.headers, json={'Amount': 20000})).status_code, 409)
        self.assertEqual((await self.client.delete(self.account_path, headers=self.headers)).status_code, 409)
        second = item['Installments'][1]['Id']
        self.assertEqual((await self.client.post(self.path + f'/installments/{second}/pay', headers=self.headers, json={})).status_code, 409)
        for bill in item['Installments']:
            result = await self.client.post(self.path + f"/installments/{bill['Id']}/pay", headers=self.headers, json={})
            self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue((await self.client.get(self.account_path, headers=self.headers)).json()['CanDelete'])
        self.assertEqual((await self.client.delete(self.account_path, headers=self.headers)).status_code, 204)

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 7))
    async def test_future_start_and_active_subscription_blocks_delete_even_when_paid(self, _):
        item = await self.subscription(first='2026-10-10')
        self.assertEqual(item['Installments'], [])
        self.assertEqual(item['NextChargeDate'], '2026-10-10')
        self.assertFalse((await self.client.get(self.account_path, headers=self.headers)).json()['CanDelete'])
        with patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 10)):
            item = (await self.client.get(self.path, headers=self.headers)).json()
            bill = item['Installments'][0]
            self.assertEqual((await self.client.post(self.path + f"/installments/{bill['Id']}/pay", headers=self.headers, json={})).status_code, 200)
            self.assertFalse((await self.client.get(self.account_path, headers=self.headers)).json()['CanDelete'])
            self.assertEqual((await self.client.delete(self.account_path, headers=self.headers)).status_code, 409)

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 7))
    async def test_nonfixed_anchor_and_history_beyond_24_months(self, _):
        item = await self.subscription(fixed=False, first='2024-05-31')
        self.assertEqual(len(item['Installments']), 29)
        self.assertEqual(item['Installments'][1]['DueDate'], '2024-06-30')
        self.assertEqual(item['Installments'][2]['DueDate'], '2024-07-31')
        self.assertTrue(all(b['DueDate'] == b['ChargedOn'] for b in item['Installments']))
        self.assertEqual((await self.client.patch(self.path + '/last-amount', headers=self.headers, json={'Amount': 1})).status_code, 409)

    async def test_conditional_input_and_fixed_due_next_month(self):
        account = (await self.create(self.card(BillingDate=20, DueDate=5))).json()
        path = '/billing/accounts/' + account['Id'] + '/transactions'
        body = {'TransactionKind': 'SUBSCRIPTION', 'Description': 'Apple', 'FirstInstallment': '2026-09-10', 'Amount': 15000}
        with patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 9, 10)):
            item = (await self.client.post(path, headers=self.headers, json=body)).json()
            self.assertEqual(item['Installments'][0]['DueDate'], '2026-10-05')
        for changes in ({'Tenor': 3}, {'LastInstallment': '2026-09-10'}, {'TransactionKind': 'OTHER'}, {'FirstInstallment': '1999-01-01'}):
            result = await self.client.post(path, headers=self.headers, json=body | changes)
            self.assertEqual(result.status_code, 422, result.text)

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 7))
    async def test_delete_future_stopped_subscription_owner_and_empty_account(self, _):
        await self.subscription(first='2026-11-19')
        self.assertEqual((await self.client.delete(self.path, headers=self.headers)).status_code, 409)
        self.assertEqual((await self.client.post(self.path + '/stop', headers=self.headers, json={})).status_code, 200)
        self.assertEqual((await self.client.delete(self.path)).status_code, 401)
        self.assertEqual((await self.client.delete(self.path, headers=self.auth_headers(self.other_id))).status_code, 404)
        removed = await self.client.delete(self.path, headers=self.headers)
        self.assertEqual(removed.status_code, 204, removed.text)
        self.assertEqual(removed.headers['cache-control'], 'no-store')
        self.assertEqual((await self.client.get(self.path, headers=self.headers)).status_code, 404)
        self.assertEqual((await self.client.get(self.account_path + '/transactions', headers=self.headers)).json(), [])
        account = await self.client.get(self.account_path, headers=self.headers)
        self.assertEqual(account.status_code, 200)
        self.assertFalse(account.json()['HasTransactions'])
        self.assertTrue(account.json()['CanDelete'])

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 10, 7))
    async def test_delete_only_after_all_issued_bills_paid_and_preserve_other_transactions(self, _):
        item = await self.subscription()
        await self.client.post(self.path + '/stop', headers=self.headers, json={})
        self.assertEqual((await self.client.delete(self.path, headers=self.headers)).status_code, 409)
        other = await self.client.post(self.account_path + '/transactions', headers=self.headers,
            json={'Description': 'Another transaction', 'Tenor': 0, 'FirstInstallment': '2026-11-01', 'LastInstallment': '2026-11-01', 'Amount': 123})
        self.assertEqual(other.status_code, 201, other.text)
        for bill in item['Installments']:
            await self.client.post(self.path + f"/installments/{bill['Id']}/pay", headers=self.headers, json={})
        removed = await self.client.delete(self.path, headers=self.headers)
        self.assertEqual(removed.status_code, 204, removed.text)
        listed = (await self.client.get(self.account_path + '/transactions', headers=self.headers)).json()
        self.assertEqual([row['Id'] for row in listed], [other.json()['Id']])
        self.assertEqual((await self.client.delete('/billing/transactions/' + other.json()['Id'], headers=self.headers)).status_code, 409)
