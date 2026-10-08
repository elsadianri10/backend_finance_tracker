import unittest
from datetime import date
from unittest.mock import patch
import test_billing as fixture


class TransactionDateTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    card = fixture.BillingTests.card
    create = fixture.BillingTests.create

    async def transaction(self, fixed=True, billing=3, due=19, **changes):
        account = (await self.create(self.card(HasFixedBillDate=fixed, BillingDate=billing if fixed else None, DueDate=due if fixed else None))).json()
        body = {'TransactionKind': 'INSTALLMENT', 'Description': 'Synthetic', 'Tenor': 3, 'TransactionDate': '2026-10-05', 'Amount': 15000} | changes
        return await self.client.post('/billing/accounts/' + account['Id'] + '/transactions', headers=self.headers, json=body)

    async def test_user_example_and_bill_dates_persist(self):
        result = await self.transaction()
        self.assertEqual(result.status_code, 201, result.text)
        item = result.json()
        self.assertEqual(item['TransactionDate'], '2026-10-05')
        self.assertEqual(item['FirstInstallment'], '2026-11-03')
        self.assertEqual(item['LastInstallment'], '2027-01-19')
        self.assertEqual([b['DueDate'] for b in item['Installments']], ['2026-11-19', '2026-12-19', '2027-01-19'])
        self.assertEqual((await self.client.get('/billing/transactions/' + item['Id'], headers=self.headers)).json(), item)

    async def test_before_and_equal_billing_day_and_single_bill(self):
        for transaction_date in ('2026-10-02', '2026-10-03'):
            result = await self.transaction(TransactionDate=transaction_date, TransactionKind='ONE_TIME', Tenor=0)
            self.assertEqual(result.status_code, 201, result.text)
            self.assertEqual(result.json()['FirstInstallment'], '2026-10-03')
            self.assertEqual(result.json()['LastInstallment'], '2026-10-19')
            self.assertEqual(len(result.json()['Installments']), 1)

    async def test_nonfixed_month_end_and_due_before_billing(self):
        result = await self.transaction(fixed=False, TransactionDate='2028-01-31')
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()['FirstInstallment'], '2028-01-31')
        self.assertEqual(result.json()['LastInstallment'], '2028-03-31')
        self.assertEqual([b['DueDate'] for b in result.json()['Installments']], ['2028-01-31', '2028-02-29', '2028-03-31'])
        result = await self.transaction(billing=20, due=5, TransactionDate='2026-12-21')
        self.assertEqual(result.json()['FirstInstallment'], '2027-01-20')
        self.assertEqual(result.json()['LastInstallment'], '2027-04-05')
        self.assertEqual([b['DueDate'] for b in result.json()['Installments']], ['2027-02-05', '2027-03-05', '2027-04-05'])
        result = await self.transaction(billing=31, due=31, TransactionDate='2028-02-29', Tenor=0, TransactionKind='ONE_TIME')
        self.assertEqual(result.json()['FirstInstallment'], '2028-02-29')
        self.assertEqual(result.json()['LastInstallment'], '2028-03-31')

    @patch('app.services.billing_transaction_service.local_today', return_value=date(2026, 11, 5))
    async def test_subscription_charge_anchor_kept_separate_from_first_billing_date(self, _):
        result = await self.transaction(TransactionKind='SUBSCRIPTION', Tenor=0)
        self.assertEqual(result.status_code, 201, result.text)
        item = result.json()
        self.assertEqual(item['FirstInstallment'], '2026-11-03')
        self.assertIsNone(item['LastInstallment'])
        self.assertEqual([b['ChargedOn'] for b in item['Installments']], ['2026-10-05', '2026-11-05'])
        self.assertEqual([b['DueDate'] for b in item['Installments']], ['2026-11-19', '2026-12-19'])
        self.assertEqual(item['NextChargeDate'], '2026-12-05')

    async def test_invalid_dates_and_mismatched_derived_dates(self):
        for changes in ({'TransactionDate': '2026-02-30'}, {'TransactionDate': '1999-12-31'}, {'FirstInstallment': '2026-10-03'}, {'LastInstallment': '2026-12-19'}):
            result = await self.transaction(**changes)
            self.assertEqual(result.status_code, 422, result.text)
