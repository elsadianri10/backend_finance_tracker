import unittest

from test_billing import BillingTests

from app.models import AccountAccess


class BudgetingTests(unittest.IsolatedAsyncioTestCase):
    pro_access = True
    asyncSetUp = BillingTests.asyncSetUp
    asyncTearDown = BillingTests.asyncTearDown
    auth_headers = BillingTests.auth_headers

    async def test_private_pro_budget_lifecycle_and_totals(self):
        payload = {
            'Name': 'December Budget', 'Months': 1, 'Categories': [
                {'Name': 'Hampers', 'Items': [
                    {'Name': 'Hampers kue', 'Seller': 'Usaha teman', 'UnitPrice': 125000, 'Quantity': 3},
                    {'Name': 'Kartu ucapan', 'Seller': 'Toko lokal', 'UnitPrice': 5000, 'Quantity': 3,
                     'Link': 'https://example.test/kartu'},
                ]},
                {'Name': 'Ongkir', 'Items': [{'Name': 'Kurir', 'UnitPrice': 25000, 'Quantity': 1}]},
            ],
        }
        created = await self.client.post('/budgeting', headers=self.headers, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.headers['cache-control'], 'no-store')
        budget = created.json()
        self.assertEqual((budget['Total'], budget['Categories'][0]['Subtotal']), (415000, 390000))
        first = budget['Categories'][0]['Items'][0]
        self.assertEqual((first['Seller'], first['Link'], first['Subtotal']), ('Usaha teman', '', 375000))
        path = '/budgeting/' + budget['Id']
        other = self.auth_headers(self.other_id)
        self.assertEqual((await self.client.get('/budgeting', headers=other)).json(), [])
        self.assertEqual((await self.client.patch(path, headers=other, json=payload | {'Version': 1})).status_code, 404)
        self.assertEqual((await self.client.delete(path + '?version=1', headers=other)).status_code, 404)

        updated = await self.client.patch(path, headers=self.headers, json=payload | {'Version': 1, 'Months': 3})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual((updated.json()['Version'], updated.json()['Months'], updated.json()['Total']), (2, 3, 415000))
        self.assertEqual((await self.client.patch(path, headers=self.headers, json=payload | {'Version': 1})).status_code, 409)
        self.assertEqual((await self.client.delete(path + '?version=1', headers=self.headers)).status_code, 409)
        self.assertEqual((await self.client.get('/budgeting', headers=self.headers)).json(), [updated.json()])
        self.assertEqual((await self.client.delete(path + '?version=2', headers=self.headers)).status_code, 204)
        self.assertEqual((await self.client.get('/budgeting', headers=self.headers)).json(), [])

    async def test_free_denied_and_invalid_items_rejected(self):
        async with self.sessions() as db:
            entry = await db.get(AccountAccess, self.other_id)
            entry.complimentary = False
            await db.commit()
        free = self.auth_headers(self.other_id)
        self.assertEqual((await self.client.get('/budgeting', headers=free)).json()['detail'], 'PRO_REQUIRED')
        self.assertEqual((await self.client.post('/budgeting', headers=free, json={'Name': 'Free'})).status_code, 403)
        item = {'Name': 'Barang', 'UnitPrice': 10000, 'Quantity': 1}
        for changes in ({'Quantity': 0}, {'UnitPrice': -1}, {'Link': 'javascript:alert(1)'}):
            response = await self.client.post('/budgeting', headers=self.headers, json={
                'Name': 'Budget', 'Categories': [{'Name': 'Umum', 'Items': [item | changes]}],
            })
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual((await self.client.get('/budgeting', headers=self.headers)).json(), [])
