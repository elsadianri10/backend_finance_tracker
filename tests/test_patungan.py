import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

import test_billing as fixture
from app.models import AccountAccess


class PatunganTests(unittest.IsolatedAsyncioTestCase):
    pro_access = True
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def test_free_cannot_read_or_change_existing_patungan(self):
        group = await self.group()
        member = await self.member(group, 'Anggota sintetis')
        payment_id = str(uuid4())
        payment = {'RequestId': payment_id, 'Amount': 26000, 'PaidOn': '2026-11-01'}
        result = await self.client.post(member + '/payments', headers=self.headers, json=payment)
        self.assertEqual(result.status_code, 204, result.text)
        async with self.sessions() as db:
            access = await db.get(AccountAccess, self.user_id)
            access.complimentary = False
            await db.commit()
        member_input = {'Name': 'Anggota sintetis', 'JoinedOn': '2026-01-01'}
        for method, path, body in (
            ('GET', '/patungan', None),
            ('GET', group + '?year=2026', None),
            ('GET', '/patungan/transactions?month=2026-11', None),
            ('POST', '/patungan', {'Name': 'Synth', 'MonthlyAmount': 26000}),
            ('PATCH', group + '/close', {'ClosedOn': '2026-11-26'}),
            ('DELETE', group, None),
            ('POST', group + '/members', member_input),
            ('PATCH', member, member_input | {'Version': 1}),
            ('PUT', member + '/waiver', {'Month': '2026-11-01', 'Waived': True}),
            ('POST', member + '/payments', payment),
            ('DELETE', member + '/payments/' + payment_id, None),
        ):
            with self.subTest(method=method, path=path):
                response = await self.client.request(method, path, headers=self.headers, json=body)
                self.assertEqual((response.status_code, response.json()['detail']), (403, 'PRO_REQUIRED'))
        async with self.sessions() as db:
            access = await db.get(AccountAccess, self.user_id)
            access.complimentary = True
            await db.commit()
        response = await self.client.get(group + '?year=2026', headers=self.headers)
        self.assertEqual(response.json()['Members'][0]['Payments'][0]['Id'], payment_id)

    async def group(self):
        response = await self.client.post('/patungan', headers=self.headers, json={
            'Name': 'Synthetic Family', 'MonthlyAmount': 26000,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return '/patungan/' + response.json()['Id']

    async def member(self, group, name, joined='2026-01-01', **extra):
        response = await self.client.post(group + '/members', headers=self.headers, json={
            'Name': name, 'JoinedOn': joined, **extra,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return '/patungan/members/' + response.json()['Id']

    async def test_payment_links_once_and_detaches_without_changing_ledger(self):
        group = await self.group()
        first = await self.member(group, 'Lany sintetis')
        second = await self.member(group, 'Teman sintetis')
        entry = {'Kind': 'income', 'Category': 'other', 'Amount': 100000,
                 'Description': 'Transfer sintetis', 'TransactionDate': '2026-11-05'}
        created = await self.client.post('/transactions', headers=self.headers, json=entry)
        self.assertEqual(created.status_code, 201, created.text)
        tx = created.json()
        tx_path = '/transactions/' + tx['Id']
        payment = {'RequestId': str(uuid4()), 'TransactionId': tx['Id']}
        other = self.auth_headers(self.other_id)
        with patch('app.services.patungan_service.local_today', return_value=date(2026, 11, 27)):
            self.assertEqual((await self.client.get(group + '?year=2026', headers=other)).status_code, 404)
            self.assertEqual((await self.client.post(first + '/payments', headers=other, json=payment)).status_code, 404)
            for _ in range(2):
                response = await self.client.post(first + '/payments', headers=self.headers, json=payment)
                self.assertEqual(response.status_code, 204, response.text)
            self.assertEqual((await self.client.post(second + '/payments', headers=self.headers,
                json=payment | {'RequestId': str(uuid4())})).status_code, 409)
            row = (await self.client.get(group + '?year=2026', headers=self.headers)).json()['Members'][0]
            self.assertEqual([part['Paid'] for part in row['Months'][:4]], [26000, 26000, 26000, 22000])
            self.assertEqual(len(row['Payments']), 1)
            self.assertEqual(row['Payments'][0]['PaidOn'], '2026-11-05')
            eligible = await self.client.get('/patungan/transactions?month=2026-11', headers=self.headers)
            self.assertEqual(eligible.json()[0]['Linked'], True)
            ledger = await self.client.get('/transactions?month=2026-11', headers=self.headers)
            self.assertEqual(ledger.json()[0]['SubscriptionReceiptId'], payment['RequestId'])
            self.assertEqual((await self.client.patch(tx_path, headers=self.headers,
                json=entry | {'Version': tx['Version']})).status_code, 409)
            self.assertEqual((await self.client.delete(tx_path, headers=self.headers)).status_code, 409)
            self.assertEqual((await self.client.delete(first + '/payments/' + payment['RequestId'],
                headers=self.headers)).status_code, 204)
            ledger = (await self.client.get('/transactions?month=2026-11', headers=self.headers)).json()
            self.assertEqual((len(ledger), ledger[0]['Id'], ledger[0]['Amount'], ledger[0]['SubscriptionReceiptId']),
                             (1, tx['Id'], 100000, None))
            self.assertEqual((await self.client.post(second + '/payments', headers=self.headers,
                json=payment | {'RequestId': str(uuid4())})).status_code, 204)

    async def test_replacement_waiver_annual_schedule_and_credit(self):
        group = await self.group()
        old = await self.member(group, 'Anggota lama', '2026-09-01', LeftOn='2026-11-15', PayAtYearEnd=True)
        replacement = await self.member(group, 'Anggota baru', '2026-11-16')
        with patch('app.services.patungan_service.local_today', return_value=date(2026, 11, 27)):
            self.assertEqual((await self.client.put(replacement + '/waiver', headers=self.headers,
                json={'Month': '2026-11-01', 'Waived': True})).status_code, 204)
            response = await self.client.post(old + '/payments', headers=self.headers, json={
                'RequestId': str(uuid4()), 'Amount': 50000, 'PaidOn': '2026-11-26',
            })
            self.assertEqual(response.status_code, 204, response.text)
            data = (await self.client.get(group + '?year=2026', headers=self.headers)).json()
            previous, current = data['Members']
            self.assertEqual([part['Paid'] for part in previous['Months'][8:11]], [26000, 24000, 0])
            self.assertEqual([part['Status'] for part in previous['Months'][9:]], ['PARTIAL', 'SCHEDULED', 'LEFT'])
            self.assertEqual(previous['Months'][10]['DueOn'], '2026-12-31')
            self.assertEqual([part['Status'] for part in current['Months'][9:]], ['NOT_JOINED', 'WAIVED', 'UPCOMING'])
            response = await self.client.post(replacement + '/payments', headers=self.headers, json={
                'RequestId': str(uuid4()), 'Amount': 78000, 'PaidOn': '2026-11-27', 'StartMonth': '2026-12-01',
            })
            self.assertEqual(response.status_code, 204, response.text)
            current = (await self.client.get(group + '?year=2026', headers=self.headers)).json()['Members'][1]
            self.assertEqual((current['Months'][11]['Paid'], current['Credit']), (26000, 52000))
            following = (await self.client.get(group + '?year=2027', headers=self.headers)).json()['Members'][1]
            self.assertEqual([part['Paid'] for part in following['Months'][:3]], [26000, 26000, 0])

    async def test_close_stops_future_iuran_and_delete_preserves_ledger(self):
        group = await self.group()
        member = await self.member(group, 'Anggota sintetis', '2026-09-01')
        other = self.auth_headers(self.other_id)
        created = await self.client.post('/transactions', headers=self.headers, json={
            'Kind': 'income', 'Category': 'other', 'Amount': 50000,
            'Description': 'Transfer sintetis', 'TransactionDate': '2026-11-05',
        })
        self.assertEqual(created.status_code, 201, created.text)
        transaction_id = created.json()['Id']
        payment = {'RequestId': str(uuid4()), 'TransactionId': transaction_id, 'StartMonth': '2026-11-01'}
        close_date = {'ClosedOn': '2026-11-26'}
        waiver = {'Month': '2026-10-01', 'Waived': True}

        with patch('app.services.patungan_service.local_today', return_value=date(2026, 11, 27)):
            self.assertEqual((await self.client.put(member + '/waiver', headers=self.headers, json=waiver)).status_code, 204)
            self.assertEqual((await self.client.post(member + '/payments', headers=self.headers, json=payment)).status_code, 204)
            self.assertEqual((await self.client.patch(group + '/close', headers=other, json=close_date)).status_code, 404)
            self.assertEqual((await self.client.patch(group + '/close', headers=self.headers,
                json={'ClosedOn': '2026-11-28'})).status_code, 422)
            for _ in range(2):
                closed = await self.client.patch(group + '/close', headers=self.headers, json=close_date)
                self.assertEqual(closed.status_code, 200, closed.text)
                self.assertEqual(closed.json()['ClosedOn'], close_date['ClosedOn'])

            detail = (await self.client.get(group + '?year=2026', headers=self.headers)).json()
            row = detail['Members'][0]
            self.assertEqual([month['Status'] for month in row['Months'][8:]], ['OVERDUE', 'WAIVED', 'PAID', 'CLOSED'])
            self.assertEqual((row['Months'][11]['Amount'], row['Months'][11]['DueOn']), (0, None))
            self.assertEqual((row['Credit'], row['Outstanding'], row['Payments'][0]['TransactionId']),
                             (24000, 26000, transaction_id))
            self.assertEqual((await self.client.post(group + '/members', headers=self.headers,
                json={'Name': 'Anggota baru', 'JoinedOn': '2026-11-27'})).status_code, 409)
            self.assertEqual((await self.client.put(member + '/waiver', headers=self.headers,
                json=waiver | {'Month': '2026-12-01'})).status_code, 422)
            manual = {'RequestId': str(uuid4()), 'Amount': 26000, 'PaidOn': '2026-11-27'}
            self.assertEqual((await self.client.post(member + '/payments', headers=self.headers,
                json=manual | {'StartMonth': '2026-12-01'})).status_code, 422)
            self.assertEqual((await self.client.post(member + '/payments', headers=self.headers,
                json=manual)).status_code, 204)
            self.assertEqual((await self.client.delete(group, headers=other)).status_code, 404)
            self.assertEqual((await self.client.delete(group, headers=self.headers)).status_code, 204)

        self.assertEqual((await self.client.get(group + '?year=2026', headers=self.headers)).status_code, 404)
        ledger = (await self.client.get('/transactions?month=2026-11', headers=self.headers)).json()
        self.assertEqual([(row['Id'], row['Amount'], row['SubscriptionReceiptId']) for row in ledger],
                         [(transaction_id, 50000, None)])
