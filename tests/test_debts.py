import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select, update

import test_billing as fixture
from app.models import Debt, DebtPayment, User


class DebtTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def create(self, **changes):
        body = {"Kind": "DEBT", "PersonName": " Budi ", "Principal": 1000000,
                "TransactionDate": "2026-01-31", "DueDate": None,
                "InterestType": "NONE", "InterestRate": 0, "Notes": "Pinjaman"} | changes
        return await self.client.post('/debts', headers=self.headers, json=body)

    async def pay(self, item, amount, day, request_id=None, **changes):
        return await self.client.post(f"/debts/{item['Id']}/payments", headers=self.headers,
                                     json={"RequestId": str(request_id or uuid4()), "Amount": amount,
                                           "PaymentDate": day, "Notes": ""} | changes)

    async def test_without_interest_partial_and_full_payment_stays_in_history(self):
        with patch('app.services.debt_service.local_today', return_value=date(2026,10,7)):
            for kind in ('DEBT', 'RECEIVABLE'):
                created = await self.create(Kind=kind)
                self.assertEqual(created.status_code, 201, created.text)
                item = created.json()
                self.assertEqual(item['PersonName'], 'Budi')
                self.assertEqual(item['InterestAccrued'], 0)
                first = await self.pay(item, 250000, '2026-02-01')
                self.assertEqual(first.status_code, 201, first.text)
                self.assertEqual(first.json()['RemainingAmount'],750000)
                last = await self.pay(item, 750000, '2026-03-01')
                self.assertEqual(last.json()['RemainingAmount'], 0)
                self.assertTrue(last.json()['IsSettled'])
                self.assertEqual(len(last.json()['Payments']), 2)
                detail = await self.client.get('/debts/'+item['Id'], headers=self.headers)
                self.assertEqual(detail.json()['PaidAmount'],1000000)
                self.assertEqual(detail.headers['cache-control'], 'no-store')
            self.assertEqual((await self.client.get('/debts', headers=self.headers)).json(), [])

    async def test_history_expires_three_calendar_months_without_deleting_records(self):
        with patch('app.services.debt_service.local_today', return_value=date(2026, 3, 31)):
            active = (await self.create(PersonName='Active')).json()
            settled = []
            for kind in ('DEBT', 'RECEIVABLE'):
                item = (await self.create(Kind=kind, InterestType='MONTHLY', InterestRate=2,
                                          InstallmentCount=2, DueDate='2026-02-28')).json()
                await self.pay(item, 220000, '2026-02-28')
                paid = await self.pay(item, 816000, '2026-03-31')
                self.assertEqual(paid.status_code, 201, paid.text)
                self.assertTrue(paid.json()['IsHistoryVisible'])
                settled.append(item)
        # March 31 + three calendar months clamps to June 30, not 90 days.
        with patch('app.services.debt_service.local_today', return_value=date(2026, 6, 29)):
            result = await self.client.get('/debts', headers=self.headers)
            self.assertEqual(len(result.json()), 3)
            self.assertEqual(result.headers['cache-control'], 'no-store')
        for today in (date(2026, 6, 30), date(2027, 1, 1)):
            with patch('app.services.debt_service.local_today', return_value=today):
                result = (await self.client.get('/debts', headers=self.headers)).json()
                self.assertEqual([item['Id'] for item in result], [active['Id']])
                for item in settled:
                    detail = await self.client.get('/debts/' + item['Id'], headers=self.headers)
                    self.assertEqual(detail.status_code, 200)
                    self.assertFalse(detail.json()['IsHistoryVisible'])
                    self.assertTrue(detail.json()['IsSettled'])
                    self.assertEqual(detail.json()['InterestAccrued'], 36000)
                    self.assertEqual(len(detail.json()['Payments']), 2)
                    self.assertEqual(len(detail.json()['Installments']), 2)
                async with self.sessions() as db:
                    self.assertEqual(len((await db.scalars(select(Debt))).all()), 3)
                    self.assertEqual(len((await db.scalars(select(DebtPayment))).all()), 4)

    async def test_month_end_reducing_principal_and_interest_first(self):
        with patch('app.services.debt_service.local_today', return_value=date(2026,3,31)):
            item = (await self.create(InterestType='MONTHLY', InterestRate='2')).json()
            self.assertEqual([c['Date'] for c in item['InterestCharges']], ['2026-02-28', '2026-03-31'])
            self.assertEqual(item['InterestAccrued'],40000)
            payment = await self.pay(item,220000,'2026-02-28')
            self.assertEqual(payment.status_code,201,payment.text)
            item = payment.json()
            self.assertEqual(item['Payments'][0]['InterestPortion'],20000)
            self.assertEqual(item['Payments'][0]['PrincipalPortion'],200000)
            self.assertEqual(item['InterestAccrued'],36000)
            self.assertEqual(item['RemainingPrincipal'],800000)
            self.assertEqual(item['RemainingInterest'],16000)
            self.assertEqual(item['RemainingAmount'],816000)
            self.assertEqual(item['NextInterestDate'],'2026-04-30')
            item = (await self.pay(item,816000,'2026-03-31')).json()
        with patch('app.services.debt_service.local_today', return_value=date(2026,10,7)):
            final = (await self.client.get('/debts/'+item['Id'],headers=self.headers)).json()
            self.assertEqual(final['InterestAccrued'],36000)
            self.assertIsNone(final['NextInterestDate'])
            self.assertTrue(final['IsSettled'])

    async def test_exact_rounding_and_no_prorata_or_compounding(self):
        with patch('app.services.debt_service.local_today', return_value=date(2026,2,27)):
            item = (await self.create(Principal=150, InterestType='MONTHLY', InterestRate='1')).json()
            self.assertEqual(item['InterestAccrued'],0)
        with patch('app.services.debt_service.local_today', return_value=date(2026,3,31)):
            item = (await self.client.get('/debts/'+item['Id'],headers=self.headers)).json()
            self.assertEqual([c['Amount'] for c in item['InterestCharges']],[2,2])
            self.assertEqual(item['RemainingAmount'],154)

    async def test_overpayment_order_future_dates_and_idempotency(self):
        with patch('app.services.debt_service.local_today', return_value=date(2026,3,31)):
            item = (await self.create()).json()
            request_id = uuid4()
            first = await self.pay(item,250000,'2026-02-01', request_id)
            again = await self.pay(item,250000,'2026-02-01', request_id)
            self.assertEqual(first.json(),again.json())
            self.assertEqual((await self.pay(item,250001,'2026-02-01',request_id)).status_code,409)
            for amount,day in ((750001,'2026-03-01'), (1,'2026-01-31'), (1,'2026-04-01'),(0,'2026-03-01'),(True,'2026-03-01')):
                self.assertEqual((await self.pay(item,amount,day)).status_code,422)
            async with self.sessions() as db:
                self.assertEqual(len((await db.scalars(select(DebtPayment))).all()),1)

    async def test_payment_amount_validated_as_of_selected_day(self):
        with patch('app.services.debt_service.local_today', return_value=date(2026,3,31)):
            item = (await self.create(InterestType='MONTHLY',InterestRate=2)).json()
            invalid = await self.pay(item,1040000,'2026-02-28')
            self.assertEqual(invalid.status_code,422)
            valid = await self.pay(item,1020000,'2026-02-28')
            self.assertTrue(valid.json()['IsSettled'])
            self.assertEqual(valid.json()['InterestAccrued'],20000)

    async def test_validation_and_overdue(self):
        with patch('app.services.debt_service.local_today', return_value=date(2026,3,31)):
            for change in ({'Kind':'BANK'},{'PersonName':' '},{'Principal':1.5},{'Principal':True},{'Principal':0},
                           {'InterestType':'NONE','InterestRate':2},{'InterestType':'MONTHLY','InterestRate':0},
                           {'InterestType':'MONTHLY','InterestRate':'1.234'},{'TransactionDate':'2026-04-01'},
                           {'TransactionDate':'1999-01-01'},{'DueDate':'2026-01-30'}):
                result = await self.create(**change)
                self.assertEqual(result.status_code,422,result.text)
                self.assertTrue(all('input' not in issue for issue in result.json()['detail']))
            item = (await self.create(DueDate='2026-02-15')).json()
            self.assertTrue(item['IsOverdue'])
            final = (await self.pay(item,1000000,'2026-03-01')).json()
            self.assertFalse(final['IsOverdue'])

    async def test_owner_scope_and_inactive_user(self):
        item = (await self.create()).json()
        path = '/debts/'+item['Id']
        other = self.auth_headers(self.other_id)
        self.assertEqual((await self.client.get('/debts',headers=other)).json(),[])
        for method in ('get','delete'):
            self.assertEqual((await getattr(self.client,method)(path,headers=other)).status_code,404)
        body = {key:item[key] for key in ('Kind','PersonName','Principal','TransactionDate','DueDate','InterestType','InterestRate','Notes')}
        self.assertEqual((await self.client.patch(path,headers=other,json=body)).status_code,404)
        self.assertEqual((await self.client.post(path+'/payments',headers=other,json={'RequestId':str(uuid4()),'Amount':1,'PaymentDate':'2026-10-07'})).status_code,404)
        self.assertEqual((await self.client.get('/debts')).status_code,401)
        async with self.sessions() as db:
            await db.execute(update(User).where(User.id==self.user_id).values(is_active=False))
            await db.commit()
        self.assertEqual((await self.client.get('/debts',headers=self.headers)).status_code,403)

    async def test_edit_and_delete_preserve_payment_history(self):
        item = (await self.create()).json()
        path = '/debts/'+item['Id']
        body = {key:item[key] for key in ('Kind','PersonName','Principal','TransactionDate','DueDate','InterestType','InterestRate','Notes')}
        changed = await self.client.patch(path,headers=self.headers,json=body|{'Principal':2000000})
        self.assertEqual(changed.status_code,200,changed.text)
        item = changed.json()
        self.assertEqual((await self.pay(item,500000,'2026-02-01')).status_code,201)
        self.assertEqual((await self.client.patch(path,headers=self.headers,json=body)).status_code,409)
        result = await self.client.patch(path,headers=self.headers,json=body|{'Principal':2000000,'PersonName':'Andi','Notes':'Updated'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['RemainingAmount'],1500000)
        self.assertEqual((await self.client.delete(path,headers=self.headers)).status_code,409)
        new = (await self.create()).json()
        self.assertEqual((await self.client.delete('/debts/'+new['Id'],headers=self.headers)).status_code,204)
        self.assertEqual((await self.client.get('/debts/'+new['Id'],headers=self.headers)).status_code,404)
