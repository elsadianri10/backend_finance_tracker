import os,unittest
from datetime import datetime,timezone
from unittest.mock import patch
from sqlalchemy import select,func
import test_billing as fixture
from app.models import User,UserAdminAudit,AccountAccess
from app.services.auth_service import google_login
class AdminRoleTests(unittest.IsolatedAsyncioTestCase):
    admin_access=True
    asyncSetUp=fixture.BillingTests.asyncSetUp
    asyncTearDown=fixture.BillingTests.asyncTearDown
    auth_headers=fixture.BillingTests.auth_headers
    def admin_headers(self,user_id=None):return fixture.BillingTests.auth_headers(self,user_id or self.user_id,portal="admin")
    async def role(self,target,flag,expected,headers=None,**extra):
        return await self.client.patch('/admin/users/'+str(target)+'/role',headers=headers or self.admin_headers(),json={'AdminF':flag,'ExpectedAdminF':expected,'Reason':'Synthetic role review',**extra})
    async def test_grant_revoke_immediate_authority_audit_and_pro_independence(self):
        target_headers=self.auth_headers(self.other_id)
        self.assertEqual((await self.client.get('/admin/access/users',headers=self.admin_headers(self.other_id))).status_code,403)
        with patch.dict(os.environ,{'ACCESS_ADMIN_EMAILS':'other@example.test'}):
            self.assertEqual((await self.role(self.user_id,0,1,headers=self.admin_headers(self.other_id))).status_code,403)
        promoted=await self.role(self.other_id,1,0);self.assertEqual(promoted.status_code,200,promoted.text);self.assertEqual(promoted.json()['AdminF'],1)
        self.assertEqual((await self.client.get('/admin/access/users',headers=self.admin_headers(self.other_id))).status_code,200)
        access=(await self.client.get('/access/me',headers=target_headers)).json();self.assertTrue(access['IsAdmin']);self.assertEqual(access['EffectivePlan'],'FREE')
        self.assertEqual((await self.role(self.other_id,0,0)).status_code,409)
        self.assertEqual((await self.role(self.other_id,0,1)).status_code,200)
        self.assertEqual((await self.client.get('/admin/access/users',headers=self.admin_headers(self.other_id))).status_code,403)
        self.assertEqual((await self.role(self.user_id,0,1,headers=self.admin_headers(self.other_id))).status_code,403)
        history=await self.client.get('/admin/users/'+str(self.other_id)+'/role-history',headers=self.admin_headers())
        self.assertEqual(len(history.json()),2);self.assertNotIn('google_sub',history.text)
        async with self.sessions() as db:self.assertEqual(await db.scalar(select(func.count()).select_from(UserAdminAudit)),2)
    async def test_owner_last_admin_strict_inputs_and_admin_cannot_request_deletion(self):
        self.assertEqual((await self.role(self.other_id,True,0)).status_code,422)
        self.assertEqual((await self.role(self.other_id,2,0)).status_code,422)
        self.assertEqual((await self.role(self.other_id,1,0,Reason='  ')).status_code,422)
        self.assertEqual((await self.role(self.user_id,0,1)).status_code,409)
        self.assertEqual((await self.client.post('/account/deletion',headers=self.headers,json={'Confirmation':'test@example.test'})).status_code,403)
        async with self.sessions() as db:
            owner=await db.get(User,self.user_id);owner.email='elsadianri10@gmail.com'
            other=await db.get(User,self.other_id);other.admin_f=1;await db.commit()
        self.assertEqual((await self.role(self.user_id,0,1)).status_code,409)
        self.assertEqual((await self.role(self.other_id,0,1)).status_code,200)
    async def test_owner_bootstrap_only_on_verified_new_google_account(self):
        claims={'sub':'synthetic-owner-first-login','email':'elsadianri10@gmail.com','name':'Owner'}
        with patch('app.services.auth_service.verify_google_token',return_value=claims),patch('app.services.passkey_service.pending_login',return_value={'Pending':True}):
            async with self.sessions() as db:
                await google_login('synthetic-token',db)
                owner=await db.scalar(select(User).where(User.google_sub==claims['sub']));self.assertEqual(owner.admin_f,1)
        claims={'sub':'synthetic-non-owner','email':'regular@example.test','name':'Regular'}
        with patch.dict(os.environ,{'ACCESS_ADMIN_EMAILS':'regular@example.test'}),patch('app.services.auth_service.verify_google_token',return_value=claims),patch('app.services.passkey_service.pending_login',return_value={'Pending':True}):
            async with self.sessions() as db:
                await google_login('synthetic-token',db)
                regular=await db.scalar(select(User).where(User.google_sub==claims['sub']));self.assertEqual(regular.admin_f,0)
