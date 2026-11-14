import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select, func
import test_billing as fixture
from app.models.access_model import AccountAccess, AccessAudit
from app.models.user_model import User
from app.services.access_service import status


class AccountAccessTests(unittest.IsolatedAsyncioTestCase):
    admin_access=True
    async def asyncSetUp(self):
        await fixture.BillingTests.asyncSetUp(self)
        self.env = patch.dict(os.environ, {'ACCESS_ADMIN_EMAILS':' test@example.test '})
        self.env.start(); self.addCleanup(self.env.stop)
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    def admin_headers(self,user_id=None):return fixture.BillingTests.auth_headers(self,user_id or self.user_id,portal="admin")

    async def change(self, **changes):
        return await self.client.patch('/admin/access/users/'+str(self.other_id), headers=self.admin_headers(),
            json={'Version':0,'Action':'GRANT','Reason':'Synthetic family access'} | changes)

    async def test_authority_separate_from_pro_and_user_privacy(self):
        self.assertEqual((await self.client.get('/access/me')).status_code,401)
        other_headers=self.auth_headers(self.other_id)
        response=await self.client.get('/access/me',headers=other_headers)
        self.assertEqual(response.json()['EffectivePlan'],'FREE')
        self.assertFalse(response.json()['IsAdmin'])
        self.assertEqual(response.headers['cache-control'],'no-store')
        for path in ('/admin/access/users','/admin/access/users/'+str(self.user_id)+'/history'):
            self.assertEqual((await self.client.get(path,headers=self.admin_headers(self.other_id))).status_code,403)
        bad=await self.client.patch('/admin/access/users/'+str(self.user_id),headers=self.admin_headers(self.other_id),
            json={'Version':0,'Action':'GRANT','Reason':'No privileges'})
        self.assertEqual(bad.status_code,403)
        self.assertEqual((await self.change()).status_code,200)
        mine=(await self.client.get('/access/me',headers=other_headers)).json()
        self.assertEqual((mine['EffectivePlan'],mine['Source'],mine['IsAdmin']),('PRO','COMPLIMENTARY',False))
        self.assertEqual((await self.client.get('/admin/access/users',headers=self.admin_headers(self.other_id))).status_code,403)
        with patch.dict(os.environ, {'ACCESS_ADMIN_EMAILS':''}):
            self.assertEqual((await self.client.get('/admin/access/users',headers=self.admin_headers())).status_code,200)
        with patch.dict(os.environ, {'ACCESS_ADMIN_EMAILS':'prefix-test@example.test'}):
            self.assertEqual((await self.client.get('/admin/access/users',headers=self.admin_headers())).status_code,200)

    async def test_grant_revoke_audit_and_stale_version(self):
        first=await self.change()
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()['Access']['Version'],1)
        self.assertEqual((await self.change()).status_code,409)
        revoked=await self.change(Version=1,Action='REVOKE',Reason='End synthetic gift')
        self.assertEqual(revoked.status_code,200,revoked.text)
        self.assertEqual(revoked.json()['Access']['EffectivePlan'],'FREE')
        async with self.sessions() as db:
            events=list(await db.scalars(select(AccessAudit)))
            self.assertEqual(len(events),2)
            self.assertTrue(all(e.actor_id == self.user_id for e in events))
            self.assertEqual(await db.scalar(select(func.count()).select_from(User)),2)
        history=await self.client.get('/admin/access/users/'+str(self.other_id)+'/history',headers=self.admin_headers())
        self.assertEqual(history.status_code,200)
        self.assertEqual(len(history.json()),2)
        self.assertTrue(all(e['ActorEmail']=='test@example.test' for e in history.json()))
        self.assertNotIn('google_sub',history.text)

    async def test_expiration_and_paid_subscription_survives_revoke(self):
        until=datetime.now(timezone.utc)+timedelta(days=5)
        first=await self.change(ExpiresAt=until.isoformat())
        self.assertEqual(first.status_code,200,first.text)
        async with self.sessions() as db:
            row=await db.get(AccountAccess,self.other_id)
            self.assertEqual(status(row,until)['EffectivePlan'],'FREE')
            row.subscription_plan='PRO';row.subscription_until=until+timedelta(days=20)
            await db.commit()
        result=await self.change(Version=1,Action='REVOKE')
        self.assertEqual(result.json()['Access']['Source'],'SUBSCRIPTION')
        async with self.sessions() as db:
            row=await db.get(AccountAccess,self.other_id)
            self.assertEqual(status(row,until+timedelta(days=20))['EffectivePlan'],'FREE')

    async def test_validation_no_partial_changes_and_safe_listing(self):
        for changes in ({'ExpiresAt':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()},
                        {'Reason':' '},{'Version':-1},{'ExpiresAt':'2026-11-12T00:00:00'},
                        {'SubscriptionPlan':'PRO'},{'Action':'ADMIN'}):
            bad=await self.change(**changes)
            self.assertEqual(bad.status_code,422,bad.text)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(AccessAudit)),0)
            user=await db.get(User,self.other_id); user.is_active=False; await db.commit()
        self.assertEqual((await self.change()).status_code,409)
        missing=await self.client.patch('/admin/access/users/'+str(uuid4()),headers=self.admin_headers(),
            json={'Version':0,'Action':'GRANT','Reason':'Synthetic'})
        self.assertEqual(missing.status_code,404)
        listed=await self.client.get('/admin/access/users?search=other&limit=1',headers=self.admin_headers())
        self.assertEqual(listed.json()['Total'],1)
        self.assertEqual(listed.json()['Items'][0]['Email'],'other@example.test')
        for field in ('google_sub','PictureUrl','auth_version','last_login_at'):
            self.assertNotIn(field,listed.text)
        self.assertEqual((await self.client.get('/admin/access/users?limit=100',headers=self.admin_headers())).status_code,422)
