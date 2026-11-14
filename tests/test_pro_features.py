import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from sqlalchemy import select, func
import test_billing as fixture
import test_routines as routine_fixture
from test_split_bills import example
from app.models import AccountAccess, RoutinePlan, SplitBillGroup, LedgerTransaction


class ProFeatureTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixture.BillingTests.asyncSetUp
    asyncTearDown=fixture.BillingTests.asyncTearDown
    auth_headers=fixture.BillingTests.auth_headers

    async def access(self,source):
        async with self.sessions() as db:
            row=await db.get(AccountAccess,self.user_id)
            if row is None:row=AccountAccess(user_id=self.user_id,version=1);db.add(row)
            at=datetime.now(timezone.utc)
            row.complimentary=source=='COMPLIMENTARY';row.complimentary_until=None
            row.subscription_plan='PRO' if source=='SUBSCRIPTION' else 'FREE'
            row.subscription_until=at+timedelta(days=1) if source=='SUBSCRIPTION' else None
            row.trial_started_at=at-timedelta(days=1) if source=='TRIAL' else None
            row.trial_until=at+timedelta(days=1) if source=='TRIAL' else None
            await db.commit()

    async def test_transaction_exports_are_free_and_records_remain(self):
        async with self.sessions() as db:
            row=LedgerTransaction(id=uuid4(),user_id=self.user_id,kind='expense',category='food',description='Synthetic',amount=1000,
                transaction_date=datetime(2026,11,2).date(),notes='',source_label='',destination_label='')
            db.add(row);await db.commit();record_id=str(row.id)
        body={'Month':'2026-11','TransactionIds':[record_id]}
        denied=await self.client.post('/transactions/export/pdf',headers=self.headers,json=body)
        self.assertEqual(denied.status_code,200)
        self.assertEqual((await self.client.post('/transactions/export/xlsx',headers=self.headers,json=body)).status_code,200)
        for source in ('TRIAL','COMPLIMENTARY','SUBSCRIPTION'):
            await self.access(source)
            result=await self.client.post('/transactions/export/pdf',headers=self.headers,json=body)
            self.assertEqual(result.status_code,200,result.text if result.status_code!=200 else source)
        await self.access('FREE')
        async with self.sessions() as db:self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)),1)

    async def test_wishlist_and_stock_require_pro_but_shared_gifts_remain_free(self):
        wishlist={'Name':'Synthetic Wishlist','Kind':'things'}
        stock={'Name':'Synthetic Vitamin','Category':'health','Subcategory':'vitamins'}
        for path,body in [('/wishlists',wishlist),('/stock-needs',stock)]:
            denied=await self.client.post(path,headers=self.headers,json=body)
            self.assertEqual(denied.status_code,403,denied.text)
            self.assertEqual(denied.json()['detail'],'PRO_REQUIRED')
        for source in ('TRIAL','COMPLIMENTARY','SUBSCRIPTION'):
            await self.access(source)
            for path,body in [('/wishlists',wishlist),('/stock-needs',stock)]:
                result=await self.client.post(path,headers=self.headers,json=body)
                self.assertEqual(result.status_code,201,result.text)
        created=(await self.client.post('/wishlists',headers=self.headers,json=wishlist)).json()
        item=(await self.client.post('/wishlists/'+created['Id']+'/items',headers=self.headers,json={'Name':'Gift','GroupId':created['Groups'][0]['Id'],'Price':1000})).json()
        product_id=item['Groups'][0]['Items'][0]['Id']
        shared=(await self.client.post('/wishlists/'+created['Id']+'/share',headers=self.headers)).json()
        token=shared.get('ShareToken') or shared.get('Token')
        self.assertIsNotNone(token,shared)
        public='/wishlists/shared/'+token
        self.assertEqual((await self.client.get(public)).status_code,200)
        self.assertEqual((await self.client.post(public+'/items/'+product_id+'/reservation',headers=self.auth_headers(self.other_id))).status_code,200)
        await self.access('FREE')
        self.assertEqual(len((await self.client.get('/wishlists',headers=self.headers)).json()),4)
        self.assertEqual(len((await self.client.get('/stock-needs',headers=self.headers)).json()),3)

    async def test_routine_new_active_limit_preserves_existing_edits(self):
        bodies=[]
        for index in range(3):
            body=routine_fixture.RoutineTests.plan(self,Name='Routine '+str(index));bodies.append(body)
            result=await self.client.post('/routine?month=2026-11',headers=self.headers,json=body)
            self.assertEqual(result.status_code,201,result.text)
        fourth=await self.client.post('/routine?month=2026-11',headers=self.headers,json=routine_fixture.RoutineTests.plan(self))
        self.assertEqual(fourth.status_code,403,fourth.text)
        await self.access('COMPLIMENTARY')
        fourth=await self.client.post('/routine?month=2026-11',headers=self.headers,json=routine_fixture.RoutineTests.plan(self))
        self.assertEqual(fourth.status_code,201,fourth.text)
        await self.access('FREE')
        updated=await self.client.patch('/routine/'+fourth.json()['Id']+'?month=2026-11',headers=self.headers,json=routine_fixture.RoutineTests.plan(self,Version=1,Name='Still editable'))
        self.assertEqual(updated.status_code,200,updated.text)
        note=await self.client.post('/routine?month=2026-11',headers=self.headers,json=routine_fixture.RoutineTests.plan(self,Status='NOTE',Amount=0))
        self.assertEqual(note.status_code,201,note.text)
        async with self.sessions() as db:self.assertEqual(await db.scalar(select(func.count()).select_from(RoutinePlan)),5)

    async def test_two_active_split_groups_and_legacy_data_untouched(self):
        body=example(2);today=datetime.now(timezone.utc).date();body['StartDate']=today.isoformat();body['EndDate']=(today+timedelta(days=10)).isoformat()
        for _ in range(2):
            response=await self.client.post('/split-bills',headers=self.headers,json=body)
            self.assertEqual(response.status_code,201,response.text)
        self.assertEqual((await self.client.post('/split-bills',headers=self.headers,json=body)).status_code,403)
        await self.access('TRIAL')
        third=await self.client.post('/split-bills',headers=self.headers,json=body);self.assertEqual(third.status_code,201,third.text)
        await self.access('FREE')
        updated=await self.client.patch('/split-bills/'+third.json()['Id'],headers=self.headers,json=body|{'Version':1,'Name':'Editable legacy'})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual((await self.client.get('/split-bills/'+third.json()['Id']+'/export',headers=self.headers)).status_code,403)
        self.assertEqual(len((await self.client.get('/split-bills',headers=self.headers)).json()),3)

    async def test_billing_debt_pro_gates_and_all_pro_sources(self):
        from fastapi import HTTPException
        from app.services import billing_transaction_service as billing, debt_service
        from app.schemas.debt_schema import PaymentCreate
        card=fixture.BillingTests.card(self)
        debt=dict(Kind='DEBT',PersonName='Synthetic Pro',Principal=1000,TransactionDate='2026-10-01',InterestType='NONE',InterestRate=0)
        for path,body in [('/billing/accounts',card),('/debts',debt)]:
            denied=await self.client.post(path,headers=self.headers,json=body)
            self.assertEqual((denied.status_code,denied.json()['detail']),(403,'PRO_REQUIRED'))
        for source in ('TRIAL','SUBSCRIPTION','COMPLIMENTARY'):
            await self.access(source)
            account=await self.client.post('/billing/accounts',headers=self.headers,json=card)
            self.assertEqual(account.status_code,201,account.text)
            created=await self.client.post('/debts',headers=self.headers,json=debt)
            self.assertEqual(created.status_code,201,created.text)
        path='/debts/'+created.json()['Id']
        await self.access('FREE')
        self.assertEqual((await self.client.get(path,headers=self.headers)).status_code,200)
        self.assertEqual((await self.client.get('/billing/accounts',headers=self.headers)).status_code,200)
        self.assertEqual((await self.client.patch(path,headers=self.headers,json=debt)).status_code,403)
        denied=await self.client.post(path+'/payments',headers=self.headers,json={'RequestId':str(uuid4()),'Amount':100,'PaymentDate':'2026-10-01','Notes':''})
        self.assertEqual(denied.status_code,403,denied.text)
        # Shared service entrypoints also cover payment through Transaksi/Rutin.
        async with self.sessions() as db:
            with self.assertRaises(HTTPException) as caught:
                await billing.mark_paid(UUID(int=1),UUID(int=2),self.user_id,db,commit=False,sync=False)
            self.assertEqual(caught.exception.detail,'PRO_REQUIRED')
            with self.assertRaises(HTTPException) as caught:
                await debt_service.add_payment(UUID(created.json()['Id']),PaymentCreate.model_validate({'RequestId':str(uuid4()),'Amount':100,'PaymentDate':'2026-10-01','Notes':''}),self.user_id,db,commit=False,sync=False)
            self.assertEqual(caught.exception.detail,'PRO_REQUIRED')
        self.assertEqual((await self.client.get(path,headers=self.headers)).status_code,200)


if __name__=='__main__':unittest.main()
