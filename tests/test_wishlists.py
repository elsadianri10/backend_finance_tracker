import unittest
from uuid import uuid4
from sqlalchemy import func, select
import test_billing as fixture
from app.models import LedgerTransaction, Saving, WishlistReservation


class WishlistTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def create(self, kind='things'):
        response = await self.client.post('/wishlists', headers=self.headers, json={'Name': 'Synthetic Wishlist', 'Kind': kind})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def item(self, row, **changes):
        response = await self.client.post('/wishlists/' + row['Id'] + '/items', headers=self.headers, json={'GroupId': row['Groups'][0]['Id'], 'Name': 'Item', 'Price': 25000} | changes)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['Groups'][0]['Items'][-1]

    async def share(self, row):
        response = await self.client.post('/wishlists/' + row['Id'] + '/share', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return '/wishlists/shared/' + response.json()['Token']

    async def test_private_owner_crud_photos_and_validation(self):
        row = await self.create()
        base = '/wishlists/' + row['Id']
        item = await self.item(row, Photos=['https://example.test/a.jpg', 'https://example.test/b.jpg'])
        self.assertEqual(len(item['Photos']), 2)
        self.assertEqual((await self.client.get('/wishlists')).status_code, 401)
        self.assertEqual((await self.client.get('/wishlists', headers=self.auth_headers(self.other_id))).json(), [])
        for method, path, payload in [('delete', base, None), ('post', base+'/share', None), ('patch', base, {'Name': 'x','Kind':'games'}), ('delete', base+'/items/'+item['Id'], None)]:
            response = await getattr(self.client, method)(path, headers=self.auth_headers(self.other_id), **({'json': payload} if payload else {}))
            self.assertEqual(response.status_code, 404)
        for changes in ({'Link': 'javascript:alert(1)'}, {'Photos': ['data:image/svg+xml,test']}, {'Price': -1}, {'GroupId': str(uuid4())}, {'Name': '   '}):
            response = await self.client.post(base+'/items', headers=self.headers, json={'Name':'x','GroupId':row['Groups'][0]['Id']} | changes)
            self.assertIn(response.status_code, (404,422))
        self.assertEqual((await self.client.delete(base, headers=self.headers)).status_code, 200)
        self.assertEqual((await self.client.get('/wishlists', headers=self.headers)).json(), [])

    async def test_guest_read_login_reservation_privacy_cancel_and_owner_override(self):
        row = await self.create()
        item = await self.item(row)
        public = await self.share(row)
        path = public + '/items/' + item['Id'] + '/reservation'
        self.assertEqual((await self.client.post(path)).status_code, 401)
        reserved = await self.client.post(path, headers=self.auth_headers(self.other_id))
        self.assertEqual(reserved.status_code, 200, reserved.text)
        self.assertTrue(reserved.json()['Groups'][0]['Items'][0]['Mine'])
        guest = await self.client.get(public)
        self.assertEqual(guest.headers['cache-control'], 'no-store')
        self.assertTrue(guest.json()['Groups'][0]['Items'][0]['Reserved'])
        self.assertIsNone(guest.json()['Groups'][0]['Items'][0]['ReservedBy'])
        owner = (await self.client.get('/wishlists', headers=self.headers)).json()[0]
        self.assertEqual(owner['Groups'][0]['Items'][0]['ReservedBy'], 'Other')
        third = self.auth_headers(uuid4())
        self.assertEqual((await self.client.delete(path, headers=third)).status_code, 401)
        self.assertEqual((await self.client.post('/wishlists/'+row['Id']+'/items/'+item['Id']+'/reservation', headers=self.headers)).status_code, 409)
        self.assertEqual((await self.client.delete('/wishlists/'+row['Id']+'/items/'+item['Id']+'/reservation', headers=self.headers)).status_code, 200)
        self.assertEqual((await self.client.post(path, headers=self.auth_headers(self.other_id))).status_code, 200)
        self.assertEqual((await self.client.delete(path, headers=self.auth_headers(self.other_id))).status_code, 200)

    async def test_view_only_and_revocation_and_wrong_item_scope(self):
        private = await self.create('vehicles')
        item = await self.item(private)
        public = await self.share(private)
        response = await self.client.get(public)
        self.assertFalse(response.json()['CanReserve'])
        self.assertEqual((await self.client.post(public+'/items/'+item['Id']+'/reservation', headers=self.auth_headers(self.other_id))).status_code, 403)
        gift = await self.create()
        gift_public = await self.share(gift)
        self.assertEqual((await self.client.post(gift_public+'/items/'+item['Id']+'/reservation', headers=self.auth_headers(self.other_id))).status_code, 404)
        new_public = await self.share(gift)
        self.assertEqual((await self.client.get(gift_public)).status_code, 404)
        self.assertEqual((await self.client.get(new_public)).status_code, 200)
        await self.client.delete('/wishlists/'+gift['Id']+'/share', headers=self.headers)
        self.assertEqual((await self.client.get(new_public)).status_code, 404)

    async def test_group_subtotal_separate_reservations_status_and_no_financial_writes(self):
        row = await self.create()
        one = await self.item(row, Name='A')
        two = await self.item(row, Name='B', Price=None)
        base = '/wishlists/'+row['Id']
        public = await self.share(row)
        await self.client.post(public+'/items/'+one['Id']+'/reservation', headers=self.auth_headers(self.other_id))
        current = (await self.client.get('/wishlists', headers=self.headers)).json()[0]
        self.assertEqual(current['Total'], 25000)
        self.assertFalse(current['Groups'][0]['Items'][1]['Reserved'])
        payload = {'GroupId':row['Groups'][0]['Id'], 'Name':'A','Price':25000,'Status':'fulfilled'}
        updated = await self.client.patch(base+'/items/'+one['Id'], headers=self.headers, json=payload)
        self.assertEqual(updated.json()['Total'], 0)
        self.assertEqual((await self.client.post(public+'/items/'+one['Id']+'/reservation', headers=self.auth_headers(self.other_id))).status_code, 409)
        await self.client.patch(base+'/items/'+two['Id'], headers=self.headers, json={'GroupId':row['Groups'][0]['Id'],'Name':'B','Status':'archived'})
        visible = (await self.client.get(public)).json()['Groups'][0]['Items']
        self.assertEqual(len(visible), 1)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Saving)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(WishlistReservation)), 0)
