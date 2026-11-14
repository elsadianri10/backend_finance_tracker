import unittest,os
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,AsyncMock
from uuid import UUID,uuid4
from sqlalchemy import select,func
import test_billing as fixture
from app.models import SubscriptionPayment, User,AccountAccess,AccountDeletion,DeletionBlob,SubscriptionOrder,Wishlist,WishlistGroup,WishlistItem,WishlistPhoto,WishlistReservation,LedgerTransaction
class DeletionTests(unittest.IsolatedAsyncioTestCase):
    admin_access=True
    asyncSetUp=fixture.BillingTests.asyncSetUp
    asyncTearDown=fixture.BillingTests.asyncTearDown
    auth_headers=fixture.BillingTests.auth_headers
    def admin_headers(self,user_id=None):return fixture.BillingTests.auth_headers(self,user_id or self.user_id,portal="admin")
    async def request(self):
        result=await self.client.post('/account/deletion',headers=self.auth_headers(self.other_id),json={'Confirmation':'other@example.test'})
        self.assertEqual(result.status_code,201,result.text);return result.json()
    async def process(self,row,action='PROCESS',confirmation=None):
        return await self.client.post('/admin/deletions/'+row['Id'],headers=self.admin_headers(),json={'Action':action,'Confirmation':confirmation if confirmation is not None else row['Id']})
    async def test_request_cancel_privacy_and_authority(self):
        self.assertEqual((await self.client.get('/account/deletion')).status_code,401)
        bad=await self.client.post('/account/deletion',headers=self.auth_headers(self.other_id),json={'Confirmation':'wrong@example.test'})
        self.assertEqual(bad.status_code,422)
        row=await self.request();self.assertEqual((await self.request())['Id'],row['Id'])
        self.assertIsNone((await self.client.get('/account/deletion',headers=self.headers)).json())
        self.assertEqual((await self.client.get('/admin/deletions',headers=self.admin_headers(self.other_id))).status_code,403)
        cancel=await self.client.post('/account/deletion/cancel',headers=self.auth_headers(self.other_id));self.assertEqual(cancel.json()['Status'],'CANCELLED')
        with patch.dict(os.environ,{'ACCESS_ADMIN_EMAILS':'test@example.test'}):
            self.assertEqual((await self.process(row)).status_code,409)
        async with self.sessions() as db:self.assertIsNotNone(await db.get(User,self.other_id))
    async def test_admin_purge_preserves_other_user_and_retries_blob_cleanup(self):
        async with self.sessions() as db:
            db.add(AccountAccess(user_id=self.other_id,complimentary=True))
            for owner in (self.user_id,self.other_id):
                db.add(LedgerTransaction(user_id=owner,kind='expense',category='food',description='Synthetic',amount=1000,transaction_date=datetime.now().date(),notes='',source_label='',destination_label=''))
            wishlist=Wishlist(id=uuid4(),user_id=self.other_id,name='Synthetic private',kind='things');db.add(wishlist);await db.flush()
            group=WishlistGroup(id=uuid4(),wishlist_id=wishlist.id,name='Synthetic');db.add(group);await db.flush()
            item=WishlistItem(id=uuid4(),group_id=group.id,name='Synthetic');db.add(item);await db.flush()
            db.add(WishlistPhoto(item_id=item.id,position=0,url='uploaded',blob_url='https://synthetic.private.blob.vercel-storage.com/wishlist/synthetic.webp'))
            db.add(WishlistReservation(item_id=item.id,user_id=self.user_id));await db.commit()
        target_headers=self.auth_headers(self.other_id)
        bank=await self.client.post('/bank-accounts',headers=target_headers,json={'PlatformId':1,'AccountNumber':'0012345678'})
        self.assertEqual(bank.status_code,201,bank.text)
        saving=await self.client.post('/savings',headers=target_headers,json={'Kind':'CASH','Name':'Synthetic saving','OpeningAmount':1000000,'StartDate':'2026-10-01','BankAccountId':bank.json()['Id']})
        self.assertEqual(saving.status_code,201,saving.text)
        debt=await self.client.post('/debts',headers=target_headers,json={'Kind':'RECEIVABLE','PersonName':'Synthetic debtor','Principal':1000,'TransactionDate':'2026-10-01','InterestType':'NONE','InterestRate':0,'SourceBankAccountId':bank.json()['Id']})
        self.assertEqual(debt.status_code,201,debt.text)
        account=await self.client.post('/billing/accounts',headers=target_headers,json={'PlatformId':2,'PlatformType':'PAY_LATER','HasFixedBillDate':False})
        self.assertEqual(account.status_code,201,account.text)
        bill=await self.client.post('/billing/accounts/'+account.json()['Id']+'/transactions',headers=target_headers,json={'Description':'Synthetic bill','Tenor':3,'FirstInstallment':'2026-10-01','LastInstallment':'2026-12-01','Amount':1000})
        self.assertEqual(bill.status_code,201,bill.text)
        row=await self.request()
        with patch.dict(os.environ,{'ACCESS_ADMIN_EMAILS':'test@example.test'}):
            self.assertEqual((await self.process(row)).status_code,409)
            self.assertEqual((await self.process(row,'REVIEW')).json()['Status'],'REVIEWING')
            self.assertEqual((await self.process(row,confirmation='wrong')).status_code,422)
            from fastapi import HTTPException
            with patch('app.services.wishlist_image_service.delete_verified',new=AsyncMock(side_effect=HTTPException(503,'retry'))):
                result=await self.process(row);self.assertEqual(result.status_code,503,result.text)
            async with self.sessions() as db:
                self.assertIsNone(await db.get(User,self.other_id));self.assertIsNotNone(await db.get(User,self.user_id))
                self.assertEqual(await db.scalar(select(func.count()).select_from(LedgerTransaction)),1)
                self.assertEqual(await db.scalar(select(func.count()).select_from(WishlistPhoto)),0)
                from app.models import BankAccount,Saving,Debt,BillingAccount,BillingTransaction,BillingInstallment
                for model in [BankAccount,Saving,Debt,BillingAccount,BillingTransaction,BillingInstallment]:self.assertEqual(await db.scalar(select(func.count()).select_from(model)),0)
                self.assertEqual((await db.get(AccountDeletion,UUID(row['Id']))).status,'CLEANUP')
                self.assertEqual(await db.scalar(select(func.count()).select_from(DeletionBlob)),1)
            self.assertEqual((await self.client.get('/auth/me',headers=self.auth_headers(self.other_id))).status_code,401)
            with patch('app.services.wishlist_image_service.delete_verified',new=AsyncMock()) as cleanup:
                result=await self.process(row);self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['Status'],'COMPLETED');cleanup.assert_awaited_once()
                self.assertEqual((await self.process(row)).json()['Status'],'COMPLETED')
            listing=await self.client.get('/admin/deletions',headers=self.admin_headers())
            self.assertIsNone(listing.json()['Items'][0]['UserEmail'])
    async def test_pending_billing_blocks_deletion_without_touching_account(self):
        async with self.sessions() as db:
            db.add(SubscriptionOrder(user_id=self.other_id,request_id=uuid4(),plan='MONTHLY',amount=29000,environment='sandbox',auto_renew=False));await db.commit()
        row=await self.request()
        with patch.dict(os.environ,{'ACCESS_ADMIN_EMAILS':'test@example.test'}):
            await self.process(row,'REVIEW');result=await self.process(row);self.assertEqual(result.status_code,409)
        async with self.sessions() as db:self.assertIsNotNone(await db.get(User,self.other_id))

    async def test_paid_history_requires_retention_review(self):
        now=datetime.now(timezone.utc)
        async with self.sessions() as db:
            order=SubscriptionOrder(id=uuid4(),user_id=self.other_id,request_id=uuid4(),plan='MONTHLY',amount=29000,environment='sandbox',auto_renew=False,state='EXPIRED')
            db.add(order);await db.flush()
            db.add(SubscriptionPayment(order_id=order.id,transaction_id='synthetic-paid',provider_order_id='synthetic-paid-order',environment='sandbox',amount=29000,state='PAID',paid_at=now,period_start=now,period_end=now+timedelta(days=30)));await db.commit()
        row=await self.request()
        with patch.dict(os.environ,{'ACCESS_ADMIN_EMAILS':'test@example.test'}):
            await self.process(row,'REVIEW');result=await self.process(row);self.assertEqual(result.status_code,409);self.assertIn('retensi',result.text)
        async with self.sessions() as db:
            self.assertIsNotNone(await db.get(User,self.other_id))
            self.assertEqual(await db.scalar(select(func.count()).select_from(SubscriptionPayment)),1)
