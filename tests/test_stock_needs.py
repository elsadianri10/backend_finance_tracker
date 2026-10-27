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

    async def test_permanent_delete_requires_archive_version_name_and_preserves_ledger(self):
        need = await self.product(await self.need())
        product = need['Products'][0]
        path = '/stock-needs/' + need['Id']
        bought = await self.client.post(path + '/products/' + product['Id'] + '/purchases', headers=self.headers, json={
            'RequestId': str(uuid4()), 'Version': product['Version'], 'Quantity': 1, 'PurchaseDate': '2026-10-01', 'Amount': 70000, 'RecordExpense': True})
        self.assertEqual(bought.status_code, 201, bought.text)
        need = bought.json()
        payload = {'Version': need['Version'], 'ConfirmationName': need['Name']}
        self.assertEqual((await self.client.request('DELETE', path, json=payload)).status_code, 401)
        self.assertEqual((await self.client.request('DELETE', path, headers=self.auth_headers(self.other_id), json=payload)).status_code, 404)
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json=payload)).status_code, 409)
        archived = (await self.client.post(path + '/actions', headers=self.headers, json={'Version': need['Version'], 'Action': 'archive'})).json()
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json=payload)).status_code, 409)
        payload['Version'] = archived['Version']
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json=payload | {'ConfirmationName': 'wrong'})).status_code, 422)
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json={'Version': archived['Version']})).status_code, 422)
        # Restoring in another tab invalidates the old delete confirmation.
        restored = (await self.client.post(path + '/actions', headers=self.headers, json={'Version': archived['Version'], 'Action': 'restore'})).json()
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json=payload)).status_code, 409)
        archived = (await self.client.post(path + '/actions', headers=self.headers, json={'Version': restored['Version'], 'Action': 'archive'})).json()
        other = await self.need(Name='Keep me')
        async with self.sessions() as db:
            row = await db.scalar(select(LedgerTransaction))
            before = tuple(getattr(row, column.name) for column in LedgerTransaction.__table__.columns)
        deleted = await self.client.request('DELETE', path, headers=self.headers, json={'Version': archived['Version'], 'ConfirmationName': need['Name']})
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()['DeletedId'], need['Id'])
        self.assertEqual(deleted.headers['cache-control'], 'no-store')
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(StockProduct)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(StockEvent)), 0)
            row = await db.scalar(select(LedgerTransaction))
            self.assertEqual(before, tuple(getattr(row, column.name) for column in LedgerTransaction.__table__.columns))
        self.assertEqual([row['Id'] for row in (await self.client.get('/stock-needs', headers=self.headers)).json()], [other['Id']])
        self.assertEqual((await self.client.get(path + '/history', headers=self.headers)).status_code, 404)

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

    async def test_delete_archived_product_preserves_parent_siblings_and_expense(self):
        need = await self.product(await self.need(), Variant='Original', ActiveCount=0, ReserveCount=0)
        product = need['Products'][0]
        base = '/stock-needs/' + need['Id']
        path = base + '/products/' + product['Id']
        bought = await self.client.post(path + '/purchases', headers=self.headers, json={
            'RequestId': str(uuid4()), 'Version': product['Version'], 'Quantity': 1, 'PurchaseDate': '2026-10-01', 'Amount': 80000, 'RecordExpense': True})
        self.assertEqual(bought.status_code, 201, bought.text)
        product = bought.json()['Products'][0]
        need = await self.product(need, Brand='Brand B')
        payload = {'Version': product['Version'], 'ConfirmationName': 'Brand A Original'}
        self.assertEqual((await self.client.request('DELETE', path, json=payload)).status_code, 401)
        self.assertEqual((await self.client.request('DELETE', path, headers=self.auth_headers(self.other_id), json=payload)).status_code, 404)
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json=payload)).status_code, 409)
        wrong_need = await self.need(Name='Other need')
        wrong_path = '/stock-needs/' + wrong_need['Id'] + '/products/' + product['Id']
        self.assertEqual((await self.client.request('DELETE', wrong_path, headers=self.headers, json=payload)).status_code, 404)
        archive = {'RequestId': str(uuid4()), 'Version': product['Version'], 'Brand': 'Brand A', 'Variant': 'Original', 'ActiveCount': 0, 'ReserveCount': 0, 'Archived': True}
        archived = await self.client.patch(path, headers=self.headers, json=archive)
        self.assertEqual(archived.status_code, 200, archived.text)
        current_product = next(p for p in archived.json()['Products'] if p['Id'] == product['Id'])
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json=payload)).status_code, 409)
        payload['Version'] = current_product['Version']
        self.assertEqual((await self.client.request('DELETE', path, headers=self.headers, json=payload | {'ConfirmationName': 'wrong'})).status_code, 422)
        async with self.sessions() as db:
            row = await db.scalar(select(LedgerTransaction))
            before = tuple(getattr(row, column.name) for column in LedgerTransaction.__table__.columns)
        removed = await self.client.request('DELETE', path, headers=self.headers, json=payload)
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()['Id'], need['Id'])
        self.assertEqual([p['Brand'] for p in removed.json()['Products']], ['Brand B'])
        self.assertGreater(removed.json()['Version'], archived.json()['Version'])
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(StockProduct)), 1)
            self.assertEqual(await db.scalar(select(func.count()).select_from(StockEvent)), 1)
            row = await db.scalar(select(LedgerTransaction))
            self.assertEqual(before, tuple(getattr(row, column.name) for column in LedgerTransaction.__table__.columns))
        history = (await self.client.get(base + '/history', headers=self.headers)).json()
        self.assertEqual([row['Brand'] for row in history], ['Brand B'])

    async def test_product_pause_skip_resume_preserve_sibling_stock_and_history(self):
        with patch('app.services.stock_service.today', return_value=date(2026, 10, 27)):
            need = await self.need(Mode='monthly', NextReview='2026-10-26')
            need = await self.product(need, ReserveCount=0)
            need = await self.product(need, Brand='Brand B', ReserveCount=0)
            a, b = need['Products']
            path = '/stock-needs/' + need['Id']
            before_history = (await self.client.get(path + '/history', headers=self.headers)).json()
            async def change(product_id, action):
                nonlocal need
                product = next(p for p in need['Products'] if p['Id'] == product_id)
                result = await self.client.post(path + '/products/' + product_id + '/replenishment', headers=self.headers, json={'Version': product['Version'], 'Action': action})
                self.assertEqual(result.status_code, 200, result.text)
                need = result.json()
            await change(a['Id'], 'pause')
            self.assertFalse(need['Products'][0]['ReplenishmentEligible'])
            self.assertTrue(need['Products'][1]['ReplenishmentEligible'])
            self.assertEqual(need['BuyReason'], 'due')
            await change(b['Id'], 'skip')
            self.assertIsNone(need['BuyReason'])
            self.assertEqual(need['Products'][1]['ReplenishmentSnoozedUntil'], '2026-11-01')
            self.assertEqual(need['NextReview'], '2026-10-26')
            self.assertEqual((await self.client.get(path + '/history', headers=self.headers)).json(), before_history)
            for old, current in zip((a, b), need['Products']):
                self.assertEqual((old['ActiveCount'], old['ReserveCount'], old['OpenedOn']), (current['ActiveCount'], current['ReserveCount'], current['OpenedOn']))
            with patch('app.services.stock_service.today', return_value=date(2026, 11, 1)):
                expired = (await self.client.get('/stock-needs', headers=self.headers)).json()[0]
                self.assertTrue(expired['Products'][1]['ReplenishmentEligible'])
                self.assertFalse(expired['Products'][0]['ReplenishmentEligible'])
            await change(a['Id'], 'resume')
            self.assertEqual(need['BuyReason'], 'due')
            self.assertFalse(need['Products'][1]['ReplenishmentEligible'])
            need = (await self.client.post(path + '/actions', headers=self.headers, json={'Version': need['Version'], 'Action': 'pause'})).json()
            await change(b['Id'], 'resume')
            self.assertTrue(need['Paused'])
            self.assertTrue(all(not p['ReplenishmentEligible'] for p in need['Products']))
            need = (await self.client.post(path + '/actions', headers=self.headers, json={'Version': need['Version'], 'Action': 'resume'})).json()
            self.assertTrue(all(p['ReplenishmentEligible'] for p in need['Products']))
            await change(a['Id'], 'pause')
            product = need['Products'][0]
            bought = await self.client.post(path + '/products/' + product['Id'] + '/purchases', headers=self.headers, json={'RequestId': str(uuid4()), 'Version': product['Version'], 'Quantity': 1, 'PurchaseDate': '2026-10-27'})
            self.assertTrue(bought.json()['Products'][0]['ReplenishmentPaused'])
            async with self.sessions() as db:
                self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)), 0)

    async def test_product_replenishment_scope_stale_version_and_archives(self):
        need = await self.product(await self.need(), ActiveCount=0, ReserveCount=0)
        product = need['Products'][0]
        path = '/stock-needs/' + need['Id'] + '/products/' + product['Id'] + '/replenishment'
        payload = {'Version': product['Version'], 'Action': 'pause'}
        self.assertEqual((await self.client.post(path, json=payload)).status_code, 401)
        self.assertEqual((await self.client.post(path, headers=self.auth_headers(self.other_id), json=payload)).status_code, 404)
        self.assertEqual((await self.client.post(path, headers=self.headers, json=payload | {'Action': 'skip'})).status_code, 422)
        changed = await self.client.post(path, headers=self.headers, json=payload)
        self.assertEqual(changed.status_code, 200)
        self.assertEqual((await self.client.post(path, headers=self.headers, json=payload)).status_code, 409)
        current = changed.json()
        archived = (await self.client.post('/stock-needs/' + need['Id'] + '/actions', headers=self.headers, json={'Version': current['Version'], 'Action': 'archive'})).json()
        self.assertEqual((await self.client.post(path, headers=self.headers, json={'Version': archived['Products'][0]['Version'], 'Action': 'resume'})).status_code, 409)

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
        product = SimpleNamespace(archived=False, reserve_count=1, near_empty=False, replenishment_paused=False, replenishment_snoozed_until=None)
        self.assertEqual(reason(need, [product], day), 'low_stock')
        need.snoozed_until = day + timedelta(days=1)
        self.assertIsNone(reason(need, [product], day))
        self.assertEqual(reason(need, [product], day + timedelta(days=1)), 'low_stock')
        need.mode, need.next_review = 'monthly', day + timedelta(days=1)
        self.assertIsNone(reason(need, [product], day))
        self.assertEqual(reason(need, [product], day + timedelta(days=1)), 'due')
