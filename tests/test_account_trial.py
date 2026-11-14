import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import select, func
import test_billing as fixture
from app.models.access_model import AccountAccess, AccessAudit
from app.models.user_model import User
from app.services.access_service import start_trial, status


class TrialTests(unittest.IsolatedAsyncioTestCase):
    admin_access=True
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    def admin_headers(self,user_id=None):return fixture.BillingTests.auth_headers(self,user_id or self.user_id,portal="admin")

    async def test_trial_starts_once_and_expires_at_exact_30_days(self):
        started=datetime(2026,11,2,3,30,tzinfo=timezone.utc)
        async with self.sessions() as db:
            user=await db.get(User,self.user_id)
            row=await start_trial(user,db,at=started);await db.commit()
            original=row.trial_started_at,row.trial_until,row.version
            trial=status(row,started)
            self.assertEqual((trial['EffectivePlan'],trial['Source'],trial['TrialDaysRemaining']),('PRO','TRIAL',30))
            self.assertEqual(trial['TrialEndsAt'],started+timedelta(days=30))
            self.assertEqual(status(row,started+timedelta(days=29,seconds=1))['TrialDaysRemaining'],1)
            expired=status(row,started+timedelta(days=30))
            self.assertEqual((expired['EffectivePlan'],expired['Source'],expired['TrialDaysRemaining']),('FREE','FREE',0))
            self.assertTrue(expired['TrialExpired'])
            await start_trial(user,db,at=started+timedelta(days=90));await db.commit()
            self.assertEqual((row.trial_started_at,row.trial_until,row.version),original)
            self.assertEqual(await db.scalar(select(func.count()).select_from(AccountAccess)),1)

    async def test_gift_and_subscription_preserved_and_trial_cannot_be_edited(self):
        started=datetime.now(timezone.utc)-timedelta(days=1)
        async with self.sessions() as db:
            user=await db.get(User,self.other_id)
            row=await start_trial(user,db,at=started)
            row.complimentary=True;row.complimentary_until=None;await db.commit()
            self.assertEqual(status(row,started+timedelta(days=90))['Source'],'COMPLIMENTARY')
        with patch.dict('os.environ',{'ACCESS_ADMIN_EMAILS':'test@example.test'}):
            revoked=await self.client.patch('/admin/access/users/'+str(self.other_id),headers=self.admin_headers(),json={
                'Version':1,'Action':'REVOKE','Reason':'Synthetic revoke'})
            self.assertEqual(revoked.status_code,200,revoked.text)
            self.assertEqual(revoked.json()['Access']['Source'],'TRIAL')
            bad=await self.client.patch('/admin/access/users/'+str(self.other_id),headers=self.admin_headers(),json={
                'Version':2,'Action':'GRANT','Reason':'Cannot reset trial','TrialEndsAt':'2099-12-31T00:00:00Z'})
            self.assertEqual(bad.status_code,422,bad.text)
        async with self.sessions() as db:
            row=await db.get(AccountAccess,self.other_id)
            self.assertEqual(status(row,started+timedelta(days=30))['Source'],'FREE')
            row.subscription_plan='PRO';row.subscription_until=started+timedelta(days=100);await db.commit()
            self.assertEqual(status(row,started+timedelta(days=31))['Source'],'SUBSCRIPTION')

    async def test_trial_dates_visible_to_user_and_admin_without_admin_rights(self):
        async with self.sessions() as db:
            user=await db.get(User,self.other_id);await start_trial(user,db);await db.commit()
        own=await self.client.get('/access/me',headers=self.auth_headers(self.other_id))
        self.assertEqual(own.status_code,200,own.text)
        self.assertEqual(own.json()['Source'],'TRIAL');self.assertFalse(own.json()['IsAdmin'])
        self.assertEqual(own.json()['TrialDaysRemaining'],30)
        self.assertTrue(own.json()['TrialStartedAt']);self.assertTrue(own.json()['TrialEndsAt'])
        self.assertEqual((await self.client.get('/admin/access/users',headers=self.admin_headers(self.other_id))).status_code,403)
        with patch.dict('os.environ',{'ACCESS_ADMIN_EMAILS':'test@example.test'}):
            listing=await self.client.get('/admin/access/users?search=other',headers=self.admin_headers())
            self.assertEqual(listing.json()['Items'][0]['Access']['TrialEndsAt'],own.json()['TrialEndsAt'])

    async def test_google_login_creates_trial_and_repeat_does_not_extend(self):
        from app.services.auth_service import google_login
        from app.config import auth_settings
        claims={'sub':'synthetic-new-trial','email':'trial@example.test','name':'Synthetic trial'}
        with patch.object(auth_settings,'require_token_settings'), patch('app.services.auth_service.verify_google_token',return_value=claims), patch('app.services.passkey_service.pending_login',return_value={'Pending':True}):
            async with self.sessions() as db:
                await google_login('synthetic',db)
                user=await db.scalar(select(User).where(User.google_sub==claims['sub']))
                row=await db.get(AccountAccess,user.id)
                initial=row.trial_started_at,row.trial_until,row.version
                await google_login('synthetic',db)
                self.assertEqual((row.trial_started_at,row.trial_until,row.version),initial)
                self.assertEqual(status(row)['Source'],'TRIAL')
                self.assertEqual(await db.scalar(select(func.count()).select_from(AccessAudit)),0)
