"""Debt/Savings integration uses an isolated in-memory database only."""
import unittest
from uuid import uuid4
from datetime import date
from unittest.mock import patch
import test_billing as fixture


class DebtSavingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixture.BillingTests.asyncSetUp(self)
        self.clock = patch('app.services.savings_service.local_today', return_value=date(2026, 10, 9))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.banks = []
        for number in ('0012345678', '0098765432'):
            r = await self.client.post('/bank-accounts', headers=self.headers, json={'PlatformId': 1, 'AccountNumber': number})
            self.assertEqual(r.status_code, 201, r.text)
            self.banks.append(r.json()['Id'])
        self.saving = await self.new_saving()

    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def new_saving(self, **changes):
        r = await self.client.post('/savings', headers=self.headers, json={
            'Kind': 'CASH', 'Name': 'Synthetic saving', 'OpeningAmount': 3000,
            'StartDate': '2026-10-01', 'BankAccountId': self.banks[0]} | changes)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()['Id']

    async def debt(self, kind='DEBT'):
        r = await self.client.post('/debts', headers=self.headers, json={
            'Kind': kind, 'PersonName': 'Synthetic', 'Principal': 2000,
            'TransactionDate': '2026-10-01', 'InterestType': 'NONE'})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()['Id']

    async def get(self, path):
        r = await self.client.get(path, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def payment(self, **changes):
        return {'RequestId': str(uuid4()), 'Amount': 500, 'PaymentDate': '2026-10-09',
                'BankAccountId': self.banks[0], 'SavingId': self.saving} | changes

    async def test_origin_both_directions_and_retry_preserve_one_transaction(self):
        for kind, balance, direction in [('DEBT', 2500, 'REMOVE'), ('RECEIVABLE', 3000, 'ADD')]:
            debt = await self.debt(kind)
            body = self.payment()
            path = '/debts/' + debt + '/payments'
            result = await self.client.post(path, headers=self.headers, json=body)
            self.assertEqual(result.status_code, 201, result.text)
            self.assertTrue(result.json()['SavingUpdated'])
            again = await self.client.post(path, headers=self.headers, json=body)
            self.assertEqual(again.json(), result.json())
            self.assertEqual(result.json()['RemainingAmount'], 1500)
            saved = await self.get('/savings/' + self.saving)
            self.assertEqual(saved['Balance'], balance)
            self.assertEqual(saved['Movements'][-1]['Direction'], direction)
            rows = await self.get('/transactions')
            linked = [r for r in rows if r['DebtPaymentId'] == result.json()['Payments'][0]['Id']]
            self.assertEqual(len(linked), 1)
            self.assertIsNotNone(linked[0]['SavingMovementId'])
            self.assertEqual(linked[0]['Kind'], 'expense' if kind == 'DEBT' else 'income')
            self.assertEqual(linked[0]['Category'], 'debt' if kind == 'DEBT' else 'receivable')
            for mutation in ({'SavingId': None}, {'BankAccountId': self.banks[1]}, {'Amount': 501}):
                bad = await self.client.post(path, headers=self.headers, json=body | mutation)
                self.assertEqual(bad.status_code, 409, bad.text)
        self.assertEqual(len(await self.get('/transactions')), 2)
        self.assertEqual(len((await self.get('/savings/' + self.saving))['Movements']), 2)

    async def test_transaction_entry_both_directions_and_cross_endpoint_retry(self):
        for kind in ('DEBT', 'RECEIVABLE'):
            debt = await self.debt(kind)
            payment = self.payment()
            body = {'RequestId': payment['RequestId'], 'DebtId': debt, 'SavingId': self.saving,
                    'Kind': 'expense' if kind == 'DEBT' else 'income',
                    'Category': 'debt' if kind == 'DEBT' else 'receivable', 'Description': 'Synthetic',
                    'Amount': 500, 'TransactionDate': '2026-10-09',
                    ('SourceBankId' if kind == 'DEBT' else 'DestinationBankId'): self.banks[0]}
            result = await self.client.post('/transactions', headers=self.headers, json=body)
            self.assertEqual(result.status_code, 201, result.text)
            self.assertTrue(result.json()['SavingMovementId'])
            again = await self.client.post('/transactions', headers=self.headers, json=body)
            self.assertEqual(again.json(), result.json())
            origin = await self.client.post('/debts/' + debt + '/payments', headers=self.headers, json=payment)
            self.assertEqual(origin.status_code, 201, origin.text)
            self.assertEqual(len(origin.json()['Payments']), 1)
        self.assertEqual((await self.get('/savings/' + self.saving))['Balance'], 3000)
        self.assertEqual(len(await self.get('/transactions')), 2)

    async def test_invalid_targets_dates_and_balances_roll_back_every_record(self):
        debt = await self.debt()
        gold = await self.new_saving(Kind='GOLD', OpeningAmount=None, BankAccountId=None,
                                     WeightPerPiece=1, Pieces=1, PricePerGram=1000)
        late = await self.new_saving(StartDate='2026-10-09')
        cases = [self.payment(Amount=2001), self.payment(BankAccountId=self.banks[1]),
                 self.payment(SavingId=str(uuid4())), self.payment(SavingId=gold, BankAccountId=None),
                 self.payment(SavingId=late, PaymentDate='2026-10-08')]
        # An otherwise valid debt amount must still fail when Savings is insufficient.
        small = await self.new_saving(OpeningAmount=100)
        cases.append(self.payment(SavingId=small))
        for body in cases:
            r = await self.client.post('/debts/' + debt + '/payments', headers=self.headers, json=body)
            self.assertIn(r.status_code, (404, 422), r.text)
            self.assertEqual((await self.get('/debts/' + debt))['RemainingAmount'], 2000)
            self.assertEqual(await self.get('/transactions'), [])
        self.assertEqual((await self.get('/savings/' + self.saving))['Balance'], 3000)
        self.assertEqual((await self.get('/savings/' + small))['Movements'], [])
        other = await self.client.post('/savings', headers=self.auth_headers(self.other_id), json={
            'Kind': 'CASH', 'Name': 'Other owner', 'OpeningAmount': 3000, 'StartDate': '2026-10-01'})
        bad = await self.client.post('/debts/' + debt + '/payments', headers=self.headers,
                                     json=self.payment(SavingId=other.json()['Id'], BankAccountId=None))
        self.assertEqual(bad.status_code, 404, bad.text)
        self.assertEqual(await self.get('/transactions'), [])

    async def test_optional_savings_and_retroactive_link_are_safe(self):
        debt = await self.debt()
        path = '/debts/' + debt + '/payments'
        body = self.payment(SavingId=None)
        result = await self.client.post(path, headers=self.headers, json=body)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertFalse(result.json()['SavingUpdated'])
        self.assertEqual((await self.get('/savings/' + self.saving))['Balance'], 3000)
        bad = await self.client.post(path, headers=self.headers, json=body | {'SavingId': self.saving})
        self.assertEqual(bad.status_code, 409, bad.text)
        self.assertEqual((await self.get('/savings/' + self.saving))['Movements'], [])
