import unittest
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select, func
import test_billing as fixture
from app.models import LedgerTransaction, StockNeed, StockProduct, StockEvent
from app.services.stock_service import reason
from types import SimpleNamespace


class StockTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def need(self, **extra):
        result = await self.client.post('/stock-needs', headers=self.headers, json={'Name': 'Sunscreen', 'Category': 'beauty', 'Subcategory': 'skincare'} | extra)
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    async def product(self, need, **extra):
        result = await self.client.post('/stock-needs/' + need['Id'] + '/products', headers=self.headers, json={
            'RequestId': str(uuid4()), 'Brand': 'Brand A', 'ActiveCount': 1, 'ReserveCount': 2} | extra)
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    async def action(self, need, action, **extra):
        product = need['Products'][0]
        return await self.client.post('/stock-needs/' + need['Id'] + '/products/' + product['Id'] + '/actions', headers=self.headers,
            json={'RequestId': str(uuid4()), 'Version': product['Version'], 'Action': action, 'EventDate': '2026-10-01'} | extra)

    async def test_package_lifecycle_history_and_idempotence(self):
        need = await self.product(await self.need())
        request_id = str(uuid4())
        first = await self.action(need, 'finish', RequestId=request_id)
        self.assertEqual(first.status_code, 200, first.text)
        updated = first.json()
        self.assertEqual((updated['Products'][0]['ActiveCount'], updated['Products'][0]['ReserveCount']), (1, 1))
        repeat = await self.action(need, 'finish', RequestId=request_id)
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(repeat.json()['Products'][0]['ReserveCount'], 1)
        self.assertEqual((await self.action(need, 'finish')).status_code, 409)
        stopped = (await self.action(updated, 'finish', OpenNext=False)).json()
        self.assertEqual((stopped['Products'][0]['ActiveCount'], stopped['Products'][0]['ReserveCount']), (0, 1))
        self.assertEqual((await self.action(stopped, 'finish')).status_code, 409)
        opened = (await self.action(stopped, 'open')).json()
        self.assertEqual((opened['Products'][0]['ActiveCount'], opened['Products'][0]['ReserveCount']), (1, 0))
        self.assertEqual(opened['BuyReason'], 'low_stock')
        history = (await self.client.get('/stock-needs/' + need['Id'] + '/history', headers=self.headers)).json()
        self.assertEqual(len(history), 4)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)), 0)

    async def test_monthly_skip_pause_and_manual_are_reminders_only(self):
        with patch('app.services.stock_service.today', return_value=date(2026, 10, 26)):
            need = await self.need(Name='Yogurt', Category='consumption', Subcategory='food', Mode='monthly', NextReview='2026-10-26')
            need = await self.product(need)
            self.assertEqual(need['BuyReason'], 'due')
            for action in ('skip', 'pause', 'resume', 'archive', 'restore'):
                response = await self.client.post('/stock-needs/' + need['Id'] + '/actions', headers=self.headers, json={'Version': need['Version'], 'Action': action})
                self.assertEqual(response.status_code, 200, response.text)
                need = response.json()
                self.assertEqual(need['Products'][0]['ReserveCount'], 2)
                if action in ('skip', 'pause', 'archive'):
                    self.assertIsNone(need['BuyReason'])
            manual = await self.need(Name='Lipstick', Mode='manual')
            manual = await self.product(manual, ReserveCount=0)
            self.assertIsNone(manual['BuyReason'])
            near = await self.action(manual, 'near_empty')
            self.assertEqual(near.json()['BuyReason'], 'near_empty')
            unmarked = await self.action(near.json(), 'not_near_empty')
            self.assertIsNone(unmarked.json()['BuyReason'])
            async with self.sessions() as db:
                self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)), 0)

    async def test_purchase_atomic_expense_optional_and_cross_owner_bank(self):
        need = await self.product(await self.need())
        product = need['Products'][0]
        path = '/stock-needs/' + need['Id'] + '/products/' + product['Id'] + '/purchases'
        payload = {'RequestId': str(uuid4()), 'Version': product['Version'], 'Quantity': 2, 'PurchaseDate': '2026-10-01', 'Amount': 230000, 'RecordExpense': True}
        invalid = await self.client.post(path, headers=self.headers, json=payload | {'SourceBankId': str(uuid4())})
        self.assertEqual(invalid.status_code, 404)
        current = (await self.client.get('/stock-needs', headers=self.headers)).json()[0]
        self.assertEqual(current['Products'][0]['ReserveCount'], 2)
        response = await self.client.post(path, headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['Products'][0]['ReserveCount'], 4)
        self.assertEqual((await self.client.post(path, headers=self.headers, json=payload)).status_code, 201)
        self.assertEqual((await self.client.post(path, headers=self.headers, json=payload | {'Quantity': 3})).status_code, 409)
        async with self.sessions() as db:
            ledgers = list(await db.scalars(select(LedgerTransaction)))
            self.assertEqual(len(ledgers), 1)
            self.assertEqual((ledgers[0].kind, ledgers[0].category, ledgers[0].amount), ('expense', 'shopping', 230000))
            self.assertEqual(await db.scalar(select(func.count()).select_from(StockEvent).where(StockEvent.kind == 'purchase')), 1)
        current = response.json()
        plain = await self.client.post(path, headers=self.headers, json={'RequestId': str(uuid4()), 'Version': current['Products'][0]['Version'], 'Quantity': 1, 'PurchaseDate': '2026-10-01'})
        self.assertEqual(plain.status_code, 201)
        self.assertEqual((await self.client.get('/stock-needs/' + need['Id'] + '/history', headers=self.auth_headers(self.other_id))).status_code, 404)

    async def test_validation_scope_brand_changes_and_read_does_not_mutate(self):
        self.assertEqual((await self.client.get('/stock-needs')).status_code, 401)
        bad = await self.client.post('/stock-needs', headers=self.headers, json={'Name': 'x', 'Category': 'health', 'Subcategory': 'makeup'})
        self.assertEqual(bad.status_code, 422)
        need = await self.product(await self.need())
        second_need = await self.need(Name='Cleanser')
        foreign = await self.client.patch('/stock-needs/' + second_need['Id'] + '/products/' + need['Products'][0]['Id'], headers=self.headers, json={'RequestId': str(uuid4()), 'Version': 1})
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual((await self.client.get('/stock-needs', headers=self.auth_headers(self.other_id))).json(), [])
        both = await self.product(need, Brand='Brand B', Preference='trial', ActiveCount=0, ReserveCount=1)
        self.assertEqual(len(both['Products']), 2)
        before = both['Products']
        for _ in range(2):
            current = (await self.client.get('/stock-needs', headers=self.headers)).json()
            self.assertEqual(next(n for n in current if n['Id'] == need['Id'])['Products'], before)
        invalid = await self.product_invalid(need)
        self.assertEqual(invalid.status_code, 422)

    async def product_invalid(self, need):
        return await self.client.post('/stock-needs/' + need['Id'] + '/products', headers=self.headers, json={'RequestId': str(uuid4()), 'ActiveCount': -1})


class ReminderTests(unittest.TestCase):
    def test_exact_threshold_snooze_and_schedule_boundaries(self):
        day = date(2026, 10, 26)
        need = SimpleNamespace(archived=False, paused=False, snoozed_until=None, buy_requested=False, mode='low_stock', reserve_threshold=1)
        product = SimpleNamespace(archived=False, reserve_count=1, near_empty=False)
        self.assertEqual(reason(need, [product], day), 'low_stock')
        need.snoozed_until = day + timedelta(days=1)
        self.assertIsNone(reason(need, [product], day))
        self.assertEqual(reason(need, [product], day + timedelta(days=1)), 'low_stock')
        need.mode, need.next_review = 'monthly', day + timedelta(days=1)
        self.assertIsNone(reason(need, [product], day))
        self.assertEqual(reason(need, [product], day + timedelta(days=1)), 'due')
