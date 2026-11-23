"""Public read-only shares use isolated in-memory data, never application records."""
import hashlib
import unittest
from uuid import UUID
from sqlalchemy import select
import test_billing as fixture
from test_split_bills import example, expense
from app.models.split_bill_model import SplitBillLink


class SplitBillSharingTests(unittest.IsolatedAsyncioTestCase):
    pro_access = False
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def make_group(self):
        body = example(2)
        body['Expenses'] = [expense(body, 150001)]
        response = await self.client.post('/split-bills', headers=self.headers, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return body, response.json()

    async def test_owner_only_rotation_revocation_and_hashed_storage(self):
        _, group = await self.make_group()
        path = '/split-bills/' + group['Id'] + '/share'
        self.assertEqual((await self.client.get(path, headers=self.headers)).json(), {'Active': False})
        for method in ['GET', 'POST', 'DELETE']:
            self.assertEqual((await self.client.request(method, path)).status_code, 401)
            self.assertEqual((await self.client.request(method, path, headers=self.auth_headers(self.other_id))).status_code, 404)
        created = await self.client.post(path, headers=self.headers)
        self.assertEqual(created.status_code, 200, created.text)
        token = created.json()['Token']
        self.assertEqual(len(token), 43)
        async with self.sessions() as db:
            link = await db.get(SplitBillLink, UUID(group['Id']))
            self.assertEqual(link.token_hash, hashlib.sha256(token.encode()).hexdigest())
            self.assertNotEqual(link.token_hash, token)
        public = await self.client.get('/split-bills/shared/' + token)
        self.assertEqual(public.status_code, 200, public.text)
        self.assertEqual(public.json(), group)
        self.assertEqual(public.headers['cache-control'], 'no-store')
        self.assertEqual(public.headers['referrer-policy'], 'no-referrer')
        self.assertNotIn('UserId', public.json())
        self.assertNotIn('Token', public.json())
        for method in ['POST', 'PATCH', 'DELETE']:
            self.assertEqual((await self.client.request(method, '/split-bills/shared/' + token)).status_code, 405)
        replacement = (await self.client.post(path, headers=self.headers)).json()['Token']
        self.assertEqual((await self.client.get('/split-bills/shared/' + token)).status_code, 404)
        self.assertEqual((await self.client.get('/split-bills/shared/' + replacement)).status_code, 200)
        self.assertEqual((await self.client.delete(path, headers=self.headers)).json(), {'Active': False})
        self.assertEqual((await self.client.get('/split-bills/shared/' + replacement)).status_code, 404)
        self.assertEqual((await self.client.delete(path, headers=self.headers)).status_code, 200)
        self.assertEqual((await self.client.get('/split-bills/shared/not-a-token')).status_code, 404)

    async def test_live_updates_and_group_deletion_invalidate_link(self):
        body, group = await self.make_group()
        path = '/split-bills/' + group['Id']
        token = (await self.client.post(path + '/share', headers=self.headers)).json()['Token']
        body['Name'] = 'Updated group'
        body['Expenses'][0]['Discount'] = 1001
        updated = await self.client.patch(path, headers=self.headers, json=body | {'Version': 1})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual((await self.client.get('/split-bills/shared/' + token)).json(), updated.json())
        self.assertEqual((await self.client.delete(path, headers=self.headers)).status_code, 204)
        self.assertEqual((await self.client.get('/split-bills/shared/' + token)).status_code, 404)
        async with self.sessions() as db:
            self.assertEqual(list(await db.scalars(select(SplitBillLink))), [])
