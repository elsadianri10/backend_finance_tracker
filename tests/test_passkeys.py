import base64
import hashlib
import json
import secrets
import unittest
from datetime import timedelta
from uuid import UUID
from unittest.mock import patch
import cbor2
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from sqlalchemy import select
import test_billing as fixture
from app.models import Passkey, PasskeyChallenge, RecoveryCode
from app.services import passkey_service as service
from app.config import auth_settings as settings


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


class Authenticator:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.id = secrets.token_bytes(32)
        self.counter = 0

    def response(self, options, register=False, origin='https://app.example.test', uv=True, rp='app.example.test'):
        client = json.dumps({'type': 'webauthn.create' if register else 'webauthn.get',
            'challenge': options['challenge'], 'origin': origin, 'crossOrigin': False}).encode()
        flags = 1 | (4 if uv else 0) | (64 if register else 0)
        self.counter += 0 if register else 1
        data = hashlib.sha256(rp.encode()).digest() + bytes([flags]) + self.counter.to_bytes(4, 'big')
        if register:
            numbers = self.key.public_key().public_numbers()
            cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')})
            data += bytes(16) + len(self.id).to_bytes(2, 'big') + self.id + cose
            response = {'clientDataJSON': b64(client), 'attestationObject': b64(cbor2.dumps({'fmt': 'none', 'attStmt': {}, 'authData': data}))}
        else:
            signature = self.key.sign(data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
            response = {'clientDataJSON': b64(client), 'authenticatorData': b64(data), 'signature': b64(signature), 'userHandle': None}
        return {'id': b64(self.id), 'rawId': b64(self.id), 'type': 'public-key', 'response': response, 'clientExtensionResults': {}}


class PasskeyTests(unittest.IsolatedAsyncioTestCase):
    auth_headers = fixture.BillingTests.auth_headers

    async def asyncSetUp(self):
        await fixture.BillingTests.asyncSetUp(self)
        self.env = patch.dict('os.environ', {'WEBAUTHN_RP_ID': 'app.example.test', 'WEBAUTHN_ORIGINS': 'https://app.example.test'})
        self.env.start()
        self.authenticator = Authenticator()

    async def asyncTearDown(self):
        self.env.stop()
        await fixture.BillingTests.asyncTearDown(self)

    def header(self, token):
        return {'Authorization': 'Bearer ' + token}

    async def enroll(self, headers=None, authenticator=None):
        headers = headers or self.headers
        authenticator = authenticator or self.authenticator
        options = await self.client.post('/passkeys/register/options', headers=headers)
        self.assertEqual(options.status_code, 200, options.text)
        value = options.json()
        result = await self.client.post('/passkeys/register/verify', headers=headers, json={
            'ChallengeId': value['ChallengeId'], 'Credential': authenticator.response(value['Options'], register=True), 'Name': 'Synthetic'})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    async def pending(self):
        with patch('app.services.auth_service.verify_google_token', return_value={
            'sub': 'billing-user', 'email': 'test@example.test', 'name': 'Test'}):
            response = await self.client.post('/auth/google', json={'IdToken': 'synthetic'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['PasskeyRequired'])
        self.assertNotIn('AccessToken', response.json())
        return self.header(response.json()['PendingToken'])

    async def assertion(self, headers, **changes):
        options = await self.client.post('/passkeys/login/options', headers=headers)
        self.assertEqual(options.status_code, 200, options.text)
        value = options.json()
        payload = {'ChallengeId': value['ChallengeId'], 'Credential': self.authenticator.response(value['Options'], **changes)}
        return payload

    async def test_enrollment_pending_login_real_signature_and_replay(self):
        registered = await self.enroll()
        self.assertEqual(len(registered['RecoveryCodes']), 8)
        self.assertEqual((await self.client.get('/auth/me', headers=self.headers)).status_code, 401)
        current = self.header(registered['AccessToken'])
        state = (await self.client.get('/passkeys', headers=current)).json()
        self.assertEqual(state['RecoveryRemaining'], 8)
        self.assertTrue(state['Enabled'])
        self.assertNotIn('PublicKey', json.dumps(state))
        pending = await self.pending()
        for path in ('/auth/me', '/bank-accounts', '/transactions', '/passkeys'):
            self.assertEqual((await self.client.get(path, headers=pending)).status_code, 401)
        payload = await self.assertion(pending)
        verified = await self.client.post('/passkeys/login/verify', headers=pending, json=payload)
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertEqual((await self.client.get('/auth/me', headers=self.header(verified.json()['AccessToken']))).status_code, 200)
        self.assertEqual((await self.client.post('/passkeys/login/verify', headers=pending, json=payload)).status_code, 401)
        self.assertEqual((await self.client.delete('/passkeys/' + state['Passkeys'][0]['Id'], headers=current)).status_code, 409)

    async def test_wrong_origin_rp_uv_owner_and_expiry_rejected(self):
        await self.enroll()
        for changes in ({'origin': 'https://evil.example.test'}, {'rp': 'evil.example.test'}, {'uv': False}):
            pending = await self.pending()
            payload = await self.assertion(pending, **changes)
            self.assertEqual((await self.client.post('/passkeys/login/verify', headers=pending, json=payload)).status_code, 401)
        pending = await self.pending()
        payload = await self.assertion(pending)
        payload['Credential']['response']['userHandle'] = b64(self.other_id.bytes)
        self.assertEqual((await self.client.post('/passkeys/login/verify', headers=pending, json=payload)).status_code, 401)
        async with self.sessions() as db:
            row = await db.get(PasskeyChallenge, UUID(payload['ChallengeId']))
            row.expires_at = service.now() - timedelta(seconds=1)
            await db.commit()
        self.assertEqual((await self.client.post('/passkeys/login/verify', headers=pending, json=payload)).status_code, 401)

    async def test_recovery_hash_one_use_and_attempt_limit(self):
        registered = await self.enroll()
        code = registered['RecoveryCodes'][0]
        async with self.sessions() as db:
            stored = list(await db.scalars(select(RecoveryCode)))
            self.assertTrue(all(code not in row.code_hash for row in stored))
        pending = await self.pending()
        recovered = await self.client.post('/passkeys/recovery', headers=pending, json={'Code': code})
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual((await self.client.get('/auth/me', headers=self.header(registered['AccessToken']))).status_code, 401)
        pending = await self.pending()
        self.assertEqual((await self.client.post('/passkeys/recovery', headers=pending, json={'Code': code})).status_code, 401)
        for _ in range(4):
            self.assertEqual((await self.client.post('/passkeys/recovery', headers=pending, json={'Code': 'wrong'})).status_code, 401)
        self.assertEqual((await self.client.post('/passkeys/recovery', headers=pending, json={'Code': registered['RecoveryCodes'][1]})).status_code, 401)

    async def test_second_key_removal_revocation_and_cross_user(self):
        registered = await self.enroll()
        current = self.header(registered['AccessToken'])
        second = await self.enroll(current, Authenticator())
        current = self.header(second['AccessToken'])
        state = (await self.client.get('/passkeys', headers=current)).json()
        self.assertEqual(len(state['Passkeys']), 2)
        key = state['Passkeys'][0]['Id']
        self.assertEqual((await self.client.delete('/passkeys/' + key, headers=self.auth_headers(self.other_id))).status_code, 404)
        removed = await self.client.delete('/passkeys/' + key, headers=current)
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual((await self.client.get('/auth/me', headers=current)).status_code, 401)
        new = self.header(removed.json()['AccessToken'])
        self.assertEqual(len((await self.client.get('/passkeys', headers=new)).json()['Passkeys']), 1)
        refreshed = await self.client.post('/passkeys/recovery-codes', headers=new)
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(len(refreshed.json()['RecoveryCodes']), 8)
        pending = await self.pending()
        self.assertEqual((await self.client.post('/passkeys/recovery', headers=pending, json={'Code': registered['RecoveryCodes'][0]})).status_code, 401)

    async def test_fresh_verification_required_and_management_unlock(self):
        initial = self.headers['Authorization'].split(' ', 1)[1]
        claims = jwt.decode(initial, settings.SECRET_KEY, algorithms=['HS256'], audience=settings.TOKEN_AUDIENCE, issuer=settings.TOKEN_ISSUER)
        claims['auth_time'] = int((service.now() - timedelta(minutes=10)).timestamp())
        stale = self.header(jwt.encode(claims, settings.SECRET_KEY, algorithm='HS256'))
        first = await self.client.post('/passkeys/register/options', headers=stale)
        self.assertEqual(first.status_code, 403)
        self.assertIn('Google', first.text)
        registered = await self.enroll()
        claims = jwt.decode(registered['AccessToken'], settings.SECRET_KEY, algorithms=['HS256'], audience=settings.TOKEN_AUDIENCE, issuer=settings.TOKEN_ISSUER)
        claims['auth_time'] = int((service.now() - timedelta(minutes=10)).timestamp())
        stale = self.header(jwt.encode(claims, settings.SECRET_KEY, algorithm='HS256'))
        self.assertEqual((await self.client.post('/passkeys/recovery-codes', headers=stale)).status_code, 403)
        options = (await self.client.post('/passkeys/manage/options', headers=stale)).json()
        result = await self.client.post('/passkeys/manage/verify', headers=stale, json={
            'ChallengeId': options['ChallengeId'], 'Credential': self.authenticator.response(options['Options'])})
        self.assertEqual(result.status_code, 200, result.text)
        fresh = self.header(result.json()['AccessToken'])
        self.assertEqual((await self.client.post('/passkeys/recovery-codes', headers=fresh)).status_code, 200)

    async def test_signature_tamper_and_cross_user_registration_challenge(self):
        options = (await self.client.post('/passkeys/register/options', headers=self.headers)).json()
        crossed = await self.client.post('/passkeys/register/verify', headers=self.auth_headers(self.other_id), json={
            'ChallengeId': options['ChallengeId'], 'Credential': self.authenticator.response(options['Options'], register=True)})
        self.assertEqual(crossed.status_code, 401)
        await self.enroll()
        pending = await self.pending()
        payload = await self.assertion(pending)
        payload['Credential']['response']['signature'] = b64(b'not-a-signature')
        self.assertEqual((await self.client.post('/passkeys/login/verify', headers=pending, json=payload)).status_code, 401)
