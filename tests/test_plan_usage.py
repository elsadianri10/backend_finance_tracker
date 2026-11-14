import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from unittest.mock import patch
import test_billing as fixture
from app.models.access_model import AccountAccess
from app.models.subscription_model import SubscriptionOrder, SubscriptionPayment

class PlanUsageTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def test_limits_archive_restore_and_legacy_data(self):
        for resource, feature, body in [
            ('bank-accounts','bankAccounts',dict(PlatformId=1, AccountNumber='001234567890', CardNumber='0123456789012345',ValidThru='2029-07',AdminFee=0,OthersFee=0)),
            ('savings','savings',dict(Kind='CASH',Name='Synthetic',OpeningAmount=1000000,StartDate='2026-10-01',Notes=''))]:
            rows=[]
            for index in range(3):
                created=await self.client.post('/'+resource,headers=self.headers,json=body)
                self.assertEqual(created.status_code,201,created.text); rows.append(created.json())
            rejected=await self.client.post('/'+resource,headers=self.headers,json=body)
            self.assertEqual((rejected.status_code,rejected.json()['detail']),(403,'PRO_REQUIRED'))
            path='/'+resource+'/'+rows[0]['Id']
            foreign=await self.client.post(path+'/archive',headers=self.auth_headers(self.other_id))
            self.assertEqual(foreign.status_code,404)
            archived=await self.client.post(path+'/archive',headers=self.headers)
            self.assertEqual(archived.status_code,200,archived.text)
            self.assertTrue(archived.json()['Archived'])
            if resource=='savings':self.assertEqual(archived.json()['Balance'],1000000)
            fourth=await self.client.post('/'+resource,headers=self.headers,json=body)
            self.assertEqual(fourth.status_code,201,fourth.text)
            self.assertEqual((await self.client.post(path+'/restore',headers=self.headers)).status_code,403)
            async with self.sessions() as db:
                row=await db.get(AccountAccess,self.user_id)
                if row is None:row=AccountAccess(user_id=self.user_id);db.add(row)
                row.complimentary=True;await db.commit()
            self.assertEqual((await self.client.post(path+'/restore',headers=self.headers)).status_code,200)
            async with self.sessions() as db:
                row=await db.get(AccountAccess,self.user_id);row.complimentary=False;await db.commit()
            usage=(await self.client.get('/access/usage',headers=self.headers)).json()
            item=next(i for i in usage['Items'] if i['Feature']==feature)
            self.assertEqual((item['Used'],item['Limit']),(4,3))
            listing=await self.client.get('/'+resource,headers=self.headers)
            self.assertEqual(listing.status_code,200)
            self.assertEqual((await self.client.patch(path,headers=self.headers,json=body)).status_code,200)
            self.assertEqual((await self.client.post(path+'/archive',headers=self.headers)).status_code,200)
        self.assertEqual((await self.client.get('/access/usage')).status_code,401)
        other=(await self.client.get('/access/usage',headers=self.auth_headers(self.other_id))).json()
        self.assertTrue(all(i['Used']==0 for i in other['Items']))

    async def test_public_catalog_and_all_entitlement_sources(self):
        catalog=await self.client.get('/plans');self.assertEqual(catalog.status_code,200)
        data=catalog.json();self.assertEqual((data['MonthlyAmount'],data['AnnualAmount']),(29000,249000))
        self.assertEqual(data['FreeLimits'],dict(bankAccounts=3,savings=3,routine=3,splitBills=2))
        self.assertNotIn('transactions',data['ProMenus']);self.assertIn('billing',data['ProMenus']);self.assertIn('debts',data['ProMenus'])
        for source in ('trial','paid','gift'):
            async with self.sessions() as db:
                row=await db.get(AccountAccess,self.user_id)
                if row is None:row=AccountAccess(user_id=self.user_id);db.add(row)
                row.trial_started_at=datetime.now(timezone.utc)-timedelta(days=1)
                row.trial_until=datetime.now(timezone.utc)+timedelta(days=29) if source=='trial' else datetime.now(timezone.utc)-timedelta(days=1)
                row.subscription_plan='PRO' if source=='paid' else 'FREE'
                row.subscription_until=datetime.now(timezone.utc)+timedelta(days=1) if source=='paid' else None
                row.complimentary=source=='gift';await db.commit()
            usage=(await self.client.get('/access/usage',headers=self.headers)).json()
            self.assertEqual(usage['EffectivePlan'],'PRO');self.assertTrue(all(i['Limit'] is None for i in usage['Items']))

    async def test_history_paginated_private_and_available_without_gateway(self):
        now=datetime.now(timezone.utc)
        async with self.sessions() as db:
            orders=[]
            for index in range(12):
                order=SubscriptionOrder(id=uuid4(),user_id=self.user_id,request_id=uuid4(),plan='MONTHLY',amount=29000,environment='sandbox',auto_renew=False,created_at=now+timedelta(seconds=index),state='PAID')
                db.add(order);orders.append(order)
            foreign=SubscriptionOrder(id=uuid4(),user_id=self.other_id,request_id=uuid4(),plan='ANNUAL',amount=249000,environment='sandbox',auto_renew=False)
            db.add(foreign);await db.flush()
            for index,state in enumerate(('PAID','REFUNDED')):
                db.add(SubscriptionPayment(id=uuid4(),order_id=orders[-1].id,transaction_id='private-provider-'+str(index),provider_order_id='private-order-'+str(index),environment='sandbox',amount=29000,state=state,paid_at=now,period_start=now,period_end=now+timedelta(days=30)))
            await db.commit()
        with patch.dict('os.environ',{'MIDTRANS_ENABLED':'false','MIDTRANS_ENVIRONMENT':'sandbox'}):
            result=await self.client.get('/subscriptions/history?limit=10',headers=self.headers)
            self.assertEqual(result.status_code,200,result.text)
            page=result.json();self.assertEqual((page['Total'],page['NextOffset'],len(page['Items'])),(12,10,10))
            self.assertEqual(len(page['Items'][0]['Payments']),2)
            self.assertNotIn('private-provider',result.text);self.assertNotIn('private-order',result.text)
            self.assertNotIn(str(foreign.id),result.text)
            last=(await self.client.get('/subscriptions/history?offset=10',headers=self.headers)).json()
            self.assertEqual(len(last['Items']),2);self.assertIsNone(last['NextOffset'])
            self.assertEqual((await self.client.get('/subscriptions/history?limit=21',headers=self.headers)).status_code,422)
            self.assertEqual((await self.client.get('/subscriptions/history')).status_code,401)
