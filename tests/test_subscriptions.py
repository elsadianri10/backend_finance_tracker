import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select, func
import test_billing as fixture
from app.models.access_model import AccountAccess
from app.models.subscription_model import SubscriptionOrder, SubscriptionPayment
from app.services import subscription_service as service


class SubscriptionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixture.BillingTests.asyncSetUp(self)
        self.env = patch.dict(os.environ, {'MIDTRANS_ENABLED':'true', 'MIDTRANS_ENVIRONMENT':'sandbox',
            'MIDTRANS_SERVER_KEY':'synthetic-key','MIDTRANS_WEBHOOK_TOKEN':'synthetic-webhook',
            'MIDTRANS_RECURRING_ENABLED':'true','SUBSCRIPTION_FRONTEND_URL':'http://localhost:3000'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.calls=[]; self.transactions={}; self.subscriptions={}; self.fail_setup=False; self.fail_cancel=False
        self.adapter=patch('app.services.midtrans_service.call',side_effect=self.gateway)
        self.adapter.start(); self.addCleanup(self.adapter.stop)
    asyncTearDown=fixture.BillingTests.asyncTearDown
    auth_headers=fixture.BillingTests.auth_headers

    async def gateway(self, method, path, payload=None, **kwargs):
        self.calls.append((method,path,payload,kwargs))
        if path == '/snap/v1/transactions':
            order=payload['transaction_details']['order_id']
            self.transactions[order]={'order_id':order,'transaction_id':'initial-'+order,'gross_amount':str(payload['transaction_details']['gross_amount']),
                'currency':'IDR','transaction_status':'pending','transaction_time':datetime.now(timezone.utc).isoformat(),
                'payment_type':'credit_card','fraud_status':'accept','saved_token_id':'secret-card-token'}
            return {'token':'never-return-this','redirect_url':'https://app.sandbox.midtrans.com/snap/v4/redirection/synthetic'}
        if path == '/v1/subscriptions':
            if self.fail_setup: raise HTTPException(502,'simulated timeout')
            subscription={'id':'synthetic-sub','name':payload['name'],'amount':payload['amount'],'currency':'IDR',
                'status':'active','transaction_ids':[], 'schedule':{'next_execution_at':payload['schedule']['start_time']}}
            self.subscriptions[subscription['id']]=subscription
            return subscription
        if path.endswith('/cancel'):
            if self.fail_cancel: raise HTTPException(502,'simulated timeout')
            self.subscriptions['synthetic-sub']['status']='inactive'
            return {'status_message':'Subscription is updated.'}
        if path.startswith('/v1/subscriptions/'):
            return self.subscriptions[path.split('/')[-1]]
        if path.startswith('/v2/pay/account/'):
            return {'account_status':'ENABLED','metadata':{'payment_options':[{'name':'GOPAY_WALLET','active':True,'token':'secret-gopay-token'}]}}
        if path.endswith('/status'):
            key=path.split('/')[2]
            if key in self.transactions:return dict(self.transactions[key])
            found=next((row for row in self.transactions.values() if row['transaction_id']==key),None)
            if found:return dict(found)
            raise HTTPException(404,'not found')
        raise AssertionError(path)

    async def checkout(self, renew=False, plan='MONTHLY', request_id=None, **extra):
        return await self.client.post('/subscriptions/checkout',headers=self.headers,json={
            'RequestId':str(request_id or uuid4()),'Plan':plan,'AutoRenew':renew,
            'ConsentVersion':'2026-11-02' if renew else None,**extra})

    async def pay(self, order_id, state='settlement'):
        key='fto_'+order_id.replace('-',''); self.transactions[key]['transaction_status']=state
        return await self.client.post('/subscriptions/orders/'+order_id+'/refresh',headers=self.headers)

    async def notify(self,payload,secret='synthetic-webhook'):
        return await self.client.post('/subscriptions/webhooks/'+secret,json=payload)

    async def test_checkout_consent_server_price_and_authorization(self):
        self.assertEqual((await self.client.get('/subscriptions/me')).status_code,401)
        self.assertEqual((await self.checkout(True,ConsentVersion=None)).status_code,422)
        self.assertEqual((await self.checkout(Amount=1)).status_code,422)
        self.assertEqual((await self.checkout(ExpectedAmount=29001)).status_code,409)
        request_id=uuid4(); response=await self.checkout(True,request_id=request_id,ExpectedAmount=29000)
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('secret',response.text); self.assertNotIn('never-return',response.text)
        self.assertEqual(response.json()['Amount'],29000)
        self.assertEqual((await self.checkout(True,request_id=request_id)).json()['Id'],response.json()['Id'])
        self.assertEqual(sum(path=='/snap/v1/transactions' for _,path,_,_ in self.calls),1)
        self.assertEqual((await self.checkout()).status_code,409)
        self.assertEqual((await self.checkout(True,plan='ANNUAL',request_id=request_id)).status_code,409)
        foreign=await self.client.post('/subscriptions/orders/'+response.json()['Id']+'/refresh',headers=self.auth_headers(self.other_id))
        self.assertEqual(foreign.status_code,404)
        async with self.sessions() as db:
            row=await db.get(SubscriptionOrder,UUID(response.json()['Id']))
            self.assertIsNotNone(row.consented_at);self.assertEqual(row.consent_version,'2026-11-02')

    async def test_pending_callback_does_not_grant_and_amount_is_verified(self):
        result=(await self.checkout()).json(); key='fto_'+result['Id'].replace('-','')
        result=await self.notify({'order_id':key,'transaction_status':'settlement','gross_amount':'1'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual((await self.client.get('/access/me',headers=self.headers)).json()['Source'],'FREE')
        self.transactions[key]['transaction_status']='settlement';self.transactions[key]['gross_amount']='1'
        self.assertEqual((await self.notify({'order_id':key})).status_code,409)
        self.assertEqual((await self.notify({'order_id':key},'bad')).status_code,404)

    async def test_paid_once_preserves_trial_and_refund_cannot_resurrect(self):
        trial_end=datetime.now(timezone.utc)+timedelta(days=20)
        async with self.sessions() as db:
            db.add(AccountAccess(user_id=self.user_id,version=1,trial_started_at=trial_end-timedelta(days=30),trial_until=trial_end));await db.commit()
        result=(await self.checkout(plan='ANNUAL')).json();order_id=result['Id']
        self.assertEqual((await self.pay(order_id)).status_code,200)
        first=(await self.client.get('/access/me',headers=self.headers)).json()
        self.assertEqual(first['Source'],'SUBSCRIPTION')
        self.assertEqual(service.provider_date(first['SubscriptionUntil']),service.add_period(trial_end,'ANNUAL'))
        self.assertEqual((await self.pay(order_id)).status_code,200)
        second=(await self.client.get('/access/me',headers=self.headers)).json()
        self.assertEqual(first['SubscriptionUntil'],second['SubscriptionUntil'])
        self.assertEqual((await self.pay(order_id,'refund')).status_code,200)
        self.assertEqual((await self.client.get('/access/me',headers=self.headers)).json()['Source'],'TRIAL')
        await self.pay(order_id,'settlement')
        self.assertEqual((await self.client.get('/access/me',headers=self.headers)).json()['Source'],'TRIAL')
        async with self.sessions() as db:self.assertEqual(await db.scalar(select(func.count()).select_from(SubscriptionPayment)),1)

    async def test_recurring_setup_cancel_and_paid_access_remains(self):
        result=(await self.checkout(True)).json(); response=await self.pay(result['Id'])
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['RenewalState'],'ACTIVE')
        self.assertIsNotNone(response.json()['NextChargeAt'])
        await self.pay(result['Id'])
        self.assertEqual(sum(path=='/v1/subscriptions' for _,path,_,_ in self.calls),1)
        before=(await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil']
        cancelled=await self.client.post('/subscriptions/orders/'+result['Id']+'/cancel-renewal',headers=self.headers)
        self.assertEqual(cancelled.status_code,200,cancelled.text)
        self.assertEqual(cancelled.json()['RenewalState'],'CANCELLED')
        self.assertIsNone(cancelled.json()['NextChargeAt'])
        self.assertEqual((await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil'],before)

    async def test_gopay_token_only_server_side_and_recurring_membership(self):
        result=(await self.checkout(True)).json();key='fto_'+result['Id'].replace('-','')
        self.transactions[key].update({'payment_type':'gopay','account_id':'synthetic-account','saved_token_id':None})
        response=await self.pay(result['Id']);self.assertEqual(response.status_code,200,response.text)
        sub=self.subscriptions['synthetic-sub']
        renewal={'order_id':sub['name']+'-123','transaction_id':'renewal-transaction','gross_amount':'29000','currency':'IDR',
            'transaction_status':'settlement','transaction_time':datetime.now(timezone.utc).isoformat(),'payment_type':'gopay'}
        self.transactions[renewal['order_id']]=renewal
        payload={'subscription':{'id':'synthetic-sub'},'transaction':{'transaction_id':'renewal-transaction'}}
        self.assertEqual((await self.notify(payload)).status_code,409)
        sub['transaction_ids']=['renewal-transaction']
        before=(await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil']
        self.assertEqual((await self.notify(payload)).status_code,200)
        after=(await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil'];self.assertGreater(after,before)
        await self.notify(payload)
        self.assertEqual((await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil'],after)
        self.assertNotIn('secret', (await self.client.get('/subscriptions/me',headers=self.headers)).text)

    async def test_ambiguous_setup_not_repeated_and_cancel_pending(self):
        result=(await self.checkout(True)).json();self.fail_setup=True
        self.assertEqual((await self.pay(result['Id'])).status_code,502)
        self.fail_setup=False
        self.assertEqual((await self.pay(result['Id'])).status_code,200)
        self.assertEqual(sum(path=='/v1/subscriptions' for _,path,_,_ in self.calls),1)
        cancelled=await self.client.post('/subscriptions/orders/'+result['Id']+'/cancel-renewal',headers=self.headers)
        self.assertEqual(cancelled.json()['RenewalState'],'REVIEW')
        self.assertIsNotNone(cancelled.json()['CancelRequestedAt'])
        self.assertEqual((await self.checkout()).status_code,409)

    async def test_cancel_before_first_payment_never_creates_recurring(self):
        result=(await self.checkout(True)).json()
        await self.client.post('/subscriptions/orders/'+result['Id']+'/cancel-renewal',headers=self.headers)
        self.assertEqual((await self.pay(result['Id'])).status_code,200)
        self.assertFalse(any(path=='/v1/subscriptions' for _,path,_,_ in self.calls))

    async def test_setup_timeout_recovered_by_creation_callback_and_honors_cancel(self):
        result=(await self.checkout(True)).json();self.fail_setup=True
        self.assertEqual((await self.pay(result['Id'])).status_code,502)
        await self.client.post('/subscriptions/orders/'+result['Id']+'/cancel-renewal',headers=self.headers)
        self.fail_setup=False
        self.subscriptions['recovered-sub']={'id':'recovered-sub','name':'ftr_'+result['Id'].replace('-',''),
            'amount':'29000','currency':'IDR','status':'active','transaction_ids':[],
            'schedule':{'next_execution_at':datetime.now(timezone.utc).isoformat()}}
        # Mock cancellation also accepts this recovered provider ID.
        self.subscriptions['synthetic-sub']=self.subscriptions['recovered-sub']
        response=await self.notify({'id':'recovered-sub','name':'ignored-untrusted-name'})
        self.assertEqual(response.status_code,200,response.text)
        order=(await self.client.get('/subscriptions/me',headers=self.headers)).json()['Orders'][0]
        self.assertEqual(order['RenewalState'],'CANCELLED')
        self.assertEqual(sum(path=='/v1/subscriptions' for _,path,_,_ in self.calls),1)

    async def test_cancel_timeout_retains_access_until_confirmed_and_inactive_callback(self):
        result=(await self.checkout(True)).json();await self.pay(result['Id'])
        self.fail_cancel=True
        self.assertEqual((await self.client.post('/subscriptions/orders/'+result['Id']+'/cancel-renewal',headers=self.headers)).status_code,502)
        row=(await self.client.get('/subscriptions/me',headers=self.headers)).json()['Orders'][0]
        self.assertIsNotNone(row['CancelRequestedAt']);self.assertNotEqual(row['RenewalState'],'CANCELLED')
        self.fail_cancel=False
        self.subscriptions['synthetic-sub']['status']='inactive'
        response=await self.notify({'subscription':{'id':'synthetic-sub'},'transaction':{'transaction_id':'failed-not-in-success-list'}})
        self.assertEqual(response.status_code,200,response.text)
        row=(await self.client.get('/subscriptions/me',headers=self.headers)).json()['Orders'][0]
        self.assertEqual(row['RenewalState'],'CANCELLED')
        self.assertEqual((await self.client.get('/access/me',headers=self.headers)).json()['Source'],'SUBSCRIPTION')

    async def test_manual_refresh_recovers_missed_recurring_and_payload_validation(self):
        result=(await self.checkout(True)).json();await self.pay(result['Id'])
        sub=self.subscriptions['synthetic-sub']
        self.transactions['missed']={'order_id':sub['name']+'-missed','transaction_id':'missed-transaction',
            'gross_amount':'29000','currency':'IDR','transaction_status':'settlement',
            'transaction_time':datetime.now(timezone.utc).isoformat(),'payment_type':'gopay'}
        sub['transaction_ids']=['missed-transaction']
        before=(await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil']
        response=await self.pay(result['Id']);self.assertEqual(response.status_code,200,response.text)
        after=(await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil'];self.assertGreater(after,before)
        self.assertEqual((await self.notify({'subscription':['bad']})).status_code,422)
        self.assertEqual((await self.client.post('/subscriptions/webhooks/synthetic-webhook',content='x'*33000)).status_code,413)

    async def test_refund_recurring_known_transaction_after_provider_list_changes(self):
        result=(await self.checkout(True)).json();await self.pay(result['Id'])
        sub=self.subscriptions['synthetic-sub']
        transaction={'order_id':sub['name']+'-refund','transaction_id':'refundable-recurring','gross_amount':'29000',
            'currency':'IDR','transaction_status':'settlement','transaction_time':datetime.now(timezone.utc).isoformat(),'payment_type':'gopay'}
        self.transactions[transaction['order_id']]=transaction;sub['transaction_ids']=['refundable-recurring']
        payload={'subscription':{'id':'synthetic-sub'},'transaction':{'transaction_id':'refundable-recurring'}}
        self.assertEqual((await self.notify(payload)).status_code,200)
        before=(await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil']
        transaction['transaction_status']='refund';sub['transaction_ids']=[]
        response=await self.notify(payload);self.assertEqual(response.status_code,200,response.text)
        after=(await self.client.get('/access/me',headers=self.headers)).json()['SubscriptionUntil'];self.assertLess(after,before)
        row=(await self.client.get('/subscriptions/me',headers=self.headers)).json()['Orders'][0]
        self.assertEqual(row['RenewalState'],'CANCELLED')

    async def test_annual_recurring_uses_supported_twelve_month_schedule(self):
        result=(await self.checkout(True,plan='ANNUAL')).json()
        response=await self.pay(result['Id']);self.assertEqual(response.status_code,200,response.text)
        body=next(payload for _,path,payload,_ in self.calls if path=='/v1/subscriptions')
        self.assertEqual(body['amount'],'249000')
        self.assertEqual(body['schedule']['interval'],12)
        self.assertEqual(body['schedule']['interval_unit'],'month')
        self.assertEqual(body['retry_schedule']['max_interval'],0)

    async def test_disabled_payments_gifts_and_calendar(self):
        with patch.dict(os.environ,{'MIDTRANS_ENABLED':'false'}):
            self.assertFalse((await self.client.get('/subscriptions/me',headers=self.headers)).json()['Enabled'])
            self.assertEqual((await self.checkout()).status_code,503)
        async with self.sessions() as db:
            db.add(AccountAccess(user_id=self.user_id,version=1,complimentary=True));await db.commit()
        self.assertEqual((await self.checkout()).status_code,409)
        self.assertEqual(service.add_period(datetime(2028,1,31,tzinfo=timezone.utc),'MONTHLY').day,29)
        self.assertEqual(service.add_period(datetime(2028,2,29,tzinfo=timezone.utc),'ANNUAL').day,28)


class MidtransAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_basic_auth_environment_and_sanitized_errors(self):
        import httpx
        from app.services import midtrans_service as gateway
        original=httpx.AsyncClient
        seen=[]
        def transport(request):
            seen.append(request)
            return httpx.Response(201,json={'token':'synthetic-snap','redirect_url':'https://app.sandbox.midtrans.com/snap/v4/redirection/test'})
        environment={'MIDTRANS_ENABLED':'true','MIDTRANS_ENVIRONMENT':'sandbox','MIDTRANS_SERVER_KEY':'adapter-secret',
            'MIDTRANS_WEBHOOK_TOKEN':'adapter-secret-webhook','SUBSCRIPTION_FRONTEND_URL':'http://localhost:3000','VERCEL_ENV':'preview'}
        with patch.dict(os.environ,environment), patch('app.services.midtrans_service.httpx.AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(transport),**kwargs)):
            await gateway.call('POST','/snap/v1/transactions',{'transaction_details':{'gross_amount':29000}},snap=True)
        self.assertEqual(str(seen[0].url),'https://app.sandbox.midtrans.com/snap/v1/transactions')
        import base64
        self.assertEqual(seen[0].headers['authorization'],'Basic '+base64.b64encode(b'adapter-secret:').decode())
        self.assertFalse(seen[0].headers.get('Idempotency-Key'))
        def failed(request):return httpx.Response(401,json={'error':'adapter-secret'})
        with patch.dict(os.environ,environment), patch('app.services.midtrans_service.httpx.AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(failed),**kwargs)):
            with self.assertRaises(HTTPException) as caught:await gateway.call('GET','/v2/test/status')
            self.assertEqual(caught.exception.status_code,502);self.assertNotIn('adapter-secret',caught.exception.detail)
        with patch.dict(os.environ,environment|{'VERCEL_ENV':'production'}):
            with self.assertRaises(HTTPException):gateway.configuration()


if __name__=='__main__':unittest.main()
