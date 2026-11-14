import unittest
from unittest.mock import patch
from sqlalchemy import select,func
import test_billing as fixture
from test_passkeys import Authenticator
from app.models import User,AccountAccess,PasskeyChallenge
from app.services.auth_service import token_claims
class AdminPortalTests(unittest.IsolatedAsyncioTestCase):
    admin_access=True
    auth_headers=fixture.BillingTests.auth_headers
    async def asyncSetUp(self):
        await fixture.BillingTests.asyncSetUp(self)
        self.env=patch.dict('os.environ',{'WEBAUTHN_RP_ID':'app.example.test','WEBAUTHN_ORIGINS':'https://app.example.test'});self.env.start();self.addCleanup(self.env.stop)
        self.authenticator=Authenticator()
    asyncTearDown=fixture.BillingTests.asyncTearDown
    def header(self,token):return {'Authorization':'Bearer '+token}
    async def google(self,admin=True,sub='billing-user',email='test@example.test'):
        with patch('app.services.auth_service.verify_google_token',return_value={'sub':sub,'email':email,'name':'Synthetic'}):
            return await self.client.post('/admin/auth/google' if admin else '/auth/google',json={'IdToken':'synthetic'})
    async def enroll(self):
        response=await self.google();self.assertEqual(response.status_code,200,response.text)
        pending=response.json()['PendingToken'];self.assertEqual(token_claims(pending,'admin_passkey_enrollment')['type'],'admin_passkey_enrollment')
        options=await self.client.post('/admin/auth/passkeys/register/options',headers=self.header(pending));self.assertEqual(options.status_code,200,options.text)
        data=options.json();verified=await self.client.post('/admin/auth/passkeys/register/verify',headers=self.header(pending),json={'ChallengeId':data['ChallengeId'],'Credential':self.authenticator.response(data['Options'],register=True),'Name':'Synthetic admin'})
        self.assertEqual(verified.status_code,200,verified.text);return verified.json()
    async def test_admin_finance_tokens_and_pending_ceremonies_are_isolated(self):
        registered=await self.enroll();admin=registered['AccessToken'];self.assertEqual(token_claims(admin,'admin_access')['type'],'admin_access')
        async with self.sessions() as db:self.assertIsNone(await db.get(AccountAccess,self.user_id))
        self.assertEqual((await self.client.get('/admin/auth/me',headers=self.header(admin))).status_code,200)
        self.assertEqual((await self.client.get('/auth/me',headers=self.header(admin))).status_code,401)
        normal_pending=(await self.google(admin=False)).json()['PendingToken']
        self.assertEqual((await self.client.post('/admin/auth/passkeys/login/options',headers=self.header(normal_pending))).status_code,401)
        options=await self.client.post('/passkeys/login/options',headers=self.header(normal_pending));data=options.json()
        verified=await self.client.post('/passkeys/login/verify',headers=self.header(normal_pending),json={'ChallengeId':data['ChallengeId'],'Credential':self.authenticator.response(data['Options'])})
        self.assertEqual(verified.status_code,200,verified.text);finance=verified.json()['AccessToken']
        self.assertEqual((await self.client.get('/auth/me',headers=self.header(finance))).status_code,200)
        self.assertEqual((await self.client.get('/admin/auth/me',headers=self.header(finance))).status_code,401)
        self.assertEqual((await self.client.get('/admin/access/users',headers=self.header(finance))).status_code,401)
        self.assertEqual((await self.client.get('/admin/access/users',headers=self.header(admin))).status_code,200)
        admin_pending=(await self.google()).json()['PendingToken']
        self.assertEqual((await self.client.post('/passkeys/login/options',headers=self.header(admin_pending))).status_code,401)
        options=await self.client.post('/admin/auth/passkeys/login/options',headers=self.header(admin_pending));self.assertEqual(options.status_code,200,options.text)
        data=options.json();verified=await self.client.post('/admin/auth/passkeys/login/verify',headers=self.header(admin_pending),json={'ChallengeId':data['ChallengeId'],'Credential':self.authenticator.response(data['Options'])})
        self.assertEqual(verified.status_code,200,verified.text)
        async with self.sessions() as db:
            user=await db.get(User,self.user_id);user.admin_f=0;await db.commit()
        self.assertEqual((await self.client.get('/admin/auth/me',headers=self.header(verified.json()['AccessToken']))).status_code,403)
        self.assertEqual((await self.client.get('/auth/me',headers=self.header(finance))).status_code,200)
    async def test_non_admin_login_does_not_register_users_or_start_trial(self):
        for sub,email in [('other-user','other@example.test'),('synthetic-new-regular','new@example.test')]:
            response=await self.google(sub=sub,email=email);self.assertEqual(response.status_code,403,response.text)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(User)),2)
            self.assertEqual(await db.scalar(select(func.count()).select_from(PasskeyChallenge)),0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(AccountAccess)),0)
    async def test_admin_recovery_stays_admin_scoped(self):
        registered=await self.enroll();pending=(await self.google()).json()['PendingToken']
        recovered=await self.client.post('/admin/auth/passkeys/recovery',headers=self.header(pending),json={'Code':registered['RecoveryCodes'][0]})
        self.assertEqual(recovered.status_code,200,recovered.text)
        token=recovered.json()['AccessToken'];self.assertEqual(token_claims(token,'admin_access')['auth_method'],'recovery')
        self.assertEqual((await self.client.get('/auth/me',headers=self.header(token))).status_code,401)
