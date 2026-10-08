import json
import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

os.environ.update(SECRET_KEY="test-secret-only-" + "x" * 48, GOOGLE_CLIENT_ID="test-client.apps.googleusercontent.com", ORIGINS="http://localhost:5173")

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from main import app, parse_origins
from app.config import auth_settings as settings
from app.config.db_config import get_db
from app.models import Base, User
from app.services.auth_service import google_rejection_reason


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def test_verification_diagnostics_do_not_expose_credentials(self):
        for message, expected in (
            ("Token has wrong audience secret-client-id", "client_id_mismatch"),
            ("Token used too early secret-token", "token_not_yet_valid_check_system_clock"),
            ("Token expired secret-token", "token_expired"),
            ("Could not verify token signature secret-token", "invalid_signature"),
            ("Malformed token secret-token", "invalid_token_format_or_claims"),
        ):
            self.assertEqual(google_rejection_reason(ValueError(message)), expected)

    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-google")])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(cls.key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                .sign(cls.key, hashes.SHA256()))
        cls.cert = cert.public_bytes(serialization.Encoding.PEM).decode()

    async def asyncSetUp(self):
        self.engine = create_async_engine(os.getenv("AUTH_TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"))
        async with self.engine.begin() as connection:
            if self.engine.dialect.name == "postgresql":
                raw = await connection.get_raw_connection()
                await raw.driver_connection.execute(Path("database/000_init.sql").read_text())
            else:
                await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        async def test_db():
            async with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        # Only the certificate download is replaced; Google's verifier executes normally.
        self.transport = patch("app.services.auth_service.GoogleRequest.__call__", return_value=SimpleNamespace(status=200, data=json.dumps({"test-key": self.cert}).encode()))
        self.transport.start()

    async def asyncTearDown(self):
        self.transport.stop()
        await self.client.aclose()
        app.dependency_overrides.clear()
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    def google_token(self, **changes):
        claims = dict(sub="google-sub-123", email="test@gmail.com", email_verified=True,
                      name="Test User", iss="https://accounts.google.com",
                      aud=settings.GOOGLE_CLIENT_ID, iat=int(time.time()) - 10, exp=int(time.time()) + 600)
        claims.update(changes)
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "test-key"})

    async def login(self, **changes):
        return await self.client.post("/auth/google", json={"IdToken": self.google_token(**changes)})

    async def test_login_reuses_user_and_updates_profile(self):
        first = await self.login()
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.headers["cache-control"], "no-store")
        second = await self.login(name="Updated", email="new@gmail.com")
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["User"]["Id"], second.json()["User"]["Id"])
        me = await self.client.get("/auth/me", headers={"Authorization": "Bearer " + second.json()["AccessToken"]})
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["Name"], "Updated")
        self.assertEqual(me.json()["Email"], "new@gmail.com")
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(User)), 1)

    async def test_invalid_google_claims_and_signature_are_rejected(self):
        for changes in ({"aud": "wrong-client"}, {"iss": "https://attacker.test"}, {"exp": int(time.time()) - 600}, {"email_verified": False}, {"sub": ""}):
            with self.subTest(changes=changes):
                response = await self.login(**changes)
                self.assertEqual(response.status_code, 401, response.text)
        token = self.google_token()
        payload = token.split(".")
        payload[1] = jwt.utils.base64url_encode(json.dumps({"sub": "attacker"}).encode()).decode()
        response = await self.client.post("/auth/google", json={"IdToken": ".".join(payload)})
        self.assertEqual(response.status_code, 401)
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(User)), 0)

    async def test_google_clock_skew_is_bounded(self):
        response = await self.login(iat=int(time.time()) + 30)
        self.assertEqual(response.status_code, 200, response.text)
        response = await self.login(iat=int(time.time()) + 120)
        self.assertEqual(response.status_code, 401, response.text)
        response = await self.login(exp=int(time.time()) - 120)
        self.assertEqual(response.status_code, 401, response.text)

    async def test_inactive_user_cannot_login_or_access_profile(self):
        login = await self.login()
        token = login.json()["AccessToken"]
        async with self.sessions() as session:
            user = await session.scalar(select(User))
            user.is_active = False
            await session.commit()
        self.assertEqual((await self.login()).status_code, 403)
        self.assertEqual((await self.client.get("/auth/me", headers={"Authorization": "Bearer " + token})).status_code, 403)

    async def test_access_tokens_are_validated(self):
        login = await self.login()
        token = login.json()["AccessToken"]
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], audience=settings.TOKEN_AUDIENCE)
        self.assertEqual((await self.client.get("/auth/me")).status_code, 401)
        self.assertEqual((await self.client.get("/auth/me", headers={"Authorization": "Bearer garbage"})).status_code, 401)
        for changes in ({"exp": int(time.time()) - 60}, {"aud": "other"}, {"iss": "other"}, {"type": "refresh"}, {"sub": "invalid-uuid"}, {"sub": str(uuid4())}):
            with self.subTest(changes=changes):
                invalid = jwt.encode(claims | changes, settings.SECRET_KEY, algorithm="HS256")
                response = await self.client.get("/auth/me", headers={"Authorization": "Bearer " + invalid})
                self.assertEqual(response.status_code, 401, response.text)
        forged = jwt.encode(claims, "another-secret-" + "x" * 48, algorithm="HS256")
        self.assertEqual((await self.client.get("/auth/me", headers={"Authorization": "Bearer " + forged})).status_code, 401)

    async def test_input_and_configuration_errors(self):
        for body in ({}, {"id_token": "x"}, {"IdToken": ""}, {"IdToken": "x", "extra": True}):
            self.assertEqual((await self.client.post("/auth/google", json=body)).status_code, 422)
        with patch.object(settings, "GOOGLE_CLIENT_ID", ""):
            self.assertEqual((await self.login()).status_code, 503)
        with patch.object(settings, "SECRET_KEY", "short"):
            self.assertEqual((await self.login()).status_code, 503)

    async def test_same_email_does_not_link_google_accounts(self):
        first = await self.login()
        second = await self.login(sub="different-google-sub")
        self.assertNotEqual(first.json()["User"]["Id"], second.json()["User"]["Id"])

    async def test_cors_and_version(self):
        response = await self.client.options("/auth/google", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertEqual((await self.client.get("/version")).status_code, 200)
        self.assertEqual(parse_origins('["http://localhost:5173"]'), ["http://localhost:5173"])
