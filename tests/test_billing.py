import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import httpx
import jwt
from sqlalchemy import event, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from main import app
from app.config import auth_settings as settings
from app.config.db_config import get_db
from app.models import Base, BillingAccount, BillingPlatform, User
from app.helpers.billing_encryption import masked_account_number


class BillingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.key_patch = patch.dict(os.environ, {"ENCRYPTION_KEY": "ab" * 32})
        self.key_patch.start()
        self.secret_patch = patch.object(settings, "SECRET_KEY", "billing-test-secret-" + "x" * 40)
        self.secret_patch.start()
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        @event.listens_for(self.engine.sync_engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.user_id = uuid4()
        self.other_id = uuid4()
        async with self.sessions() as db:
            now = datetime.now(timezone.utc)
            db.add_all([
                User(id=self.user_id, google_sub="billing-user", email="test@example.test", name="Test", last_login_at=now),
                User(id=self.other_id, google_sub="other-user", email="other@example.test", name="Other", last_login_at=now),
                BillingPlatform(id=1, name="BCA", bank_f=1), BillingPlatform(id=2, name="GoPay Later"),
                BillingPlatform(id=3, name="Inactive", is_active=False),
            ])
            await db.flush()
            await db.commit()
        async def test_db():
            async with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = test_db
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.headers = self.auth_headers(self.user_id)

    def auth_headers(self, user_id):
        now = datetime.now(timezone.utc)
        token = jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=5), "type": "access", "iss": settings.TOKEN_ISSUER, "aud": settings.TOKEN_AUDIENCE}, settings.SECRET_KEY, algorithm="HS256")
        return {"Authorization": "Bearer " + token}

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.client.aclose()
        await self.engine.dispose()
        self.key_patch.stop()
        self.secret_patch.stop()

    def card(self, **changes):
        return {"PlatformId": 1, "PlatformType": "CREDIT_CARD", "AccountType": "BCA Batman", "AccountNumber": "0123456789012345", "ValidThru": "2029-07", "HasFixedBillDate": True, "BillingDate": 20, "DueDate": 5} | changes

    async def create(self, payload):
        return await self.client.post("/billing/accounts", headers=self.headers, json=payload)

    async def test_card_is_encrypted_and_only_masked_in_responses(self):
        response = await self.create(self.card())
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["AccountNumberMasked"], "************2345")
        self.assertNotIn("AccountNumber", result)
        self.assertNotIn(self.card()["AccountNumber"], response.text)
        async with self.sessions() as db:
            account = await db.scalar(select(BillingAccount))
            self.assertNotIn(self.card()["AccountNumber"], account.account_number_encrypted)
            self.assertEqual(masked_account_number(account.account_number_encrypted, account.id, account.user_id), result["AccountNumberMasked"])
            with self.assertRaises(Exception):
                masked_account_number(account.account_number_encrypted, uuid4(), account.user_id)
        listed = await self.client.get("/billing/accounts", headers=self.headers)
        self.assertEqual(listed.json()[0]["Id"], result["Id"])
        self.assertNotIn(self.card()["AccountNumber"], listed.text)
        detail = await self.client.get("/billing/accounts/" + result["Id"], headers=self.headers)
        self.assertEqual(detail.status_code, 200)

    async def test_platforms_are_loaded_from_database_and_inactive_rejected(self):
        response = await self.client.get("/billing/platforms", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"Id": 1, "Name": "BCA", "BankF": 1, "SupportedTypes": ["CREDIT_CARD", "PAY_LATER"]}, {"Id": 2, "Name": "GoPay Later", "BankF": 0, "SupportedTypes": ["CREDIT_CARD", "PAY_LATER"]}])
        for platform_id in (3, 999):
            self.assertEqual((await self.create(self.card(PlatformId=platform_id))).status_code, 422)

    async def test_paylater_accepts_fixed_and_nonfixed_dates_without_card_fields(self):
        for fixed in (True, False):
            payload = {"PlatformId": 2, "PlatformType": "PAY_LATER", "HasFixedBillDate": fixed}
            if fixed:
                payload |= {"BillingDate": 1, "DueDate": 15}
            response = await self.create(payload)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertIsNone(response.json()["AccountNumberMasked"])
        response = await self.create(self.card(HasFixedBillDate=False, BillingDate=None, DueDate=None))
        self.assertEqual(response.status_code, 201, response.text)

    async def test_name_only_platform_supports_both_account_types_and_edit(self):
        async with self.sessions() as db:
            db.add(BillingPlatform(id=4, name="Blibli Pay Later"))
            await db.commit()
        listed = await self.client.get("/billing/platforms", headers=self.headers)
        platform = next(item for item in listed.json() if item["Id"] == 4)
        self.assertEqual(platform["SupportedTypes"], ["CREDIT_CARD", "PAY_LATER"])
        pay = await self.create({"PlatformId": 4, "PlatformType": "PAY_LATER", "HasFixedBillDate": False})
        self.assertEqual(pay.status_code, 201, pay.text)
        card = await self.create(self.card(PlatformId=4))
        self.assertEqual(card.status_code, 201, card.text)
        edited = await self.client.patch("/billing/accounts/" + pay.json()["Id"], headers=self.headers,
                                       json=self.card(PlatformId=4))
        self.assertEqual(edited.status_code, 200, edited.text)

    async def test_account_type_restricted_in_api_and_database(self):
        for invalid in (None, "BANK", "", "pay_later"):
            response = await self.create({"PlatformId": 2, "PlatformType": invalid, "HasFixedBillDate": False})
            self.assertEqual(response.status_code, 422, response.text)
        created = await self.create({"PlatformId": 1, "PlatformType": "PAY_LATER", "HasFixedBillDate": False})
        self.assertEqual(created.status_code, 201, created.text)
        for invalid in (None, "BANK", "", "pay_later"):
            async with self.sessions() as db:
                with self.assertRaises(IntegrityError):
                    await db.execute(update(BillingAccount).values(platform_type=invalid))
                await db.rollback()

    async def test_conditional_fields_are_validated_and_sensitive_inputs_not_echoed(self):
        for changes in ({"AccountType": None}, {"AccountType": "   "}, {"AccountNumber": None}, {"AccountNumber": 1234567890123456}, {"ValidThru": None}, {"ValidThru": "2029-13"}, {"BillingDate": None}, {"DueDate": 0}, {"DueDate": 32}, {"BillingDate": True}, {"HasFixedBillDate": "false"}, {"HasFixedBillDate": False}):
            with self.subTest(changes=changes):
                response = await self.create(self.card(**changes))
                self.assertEqual(response.status_code, 422, response.text)
                self.assertNotIn("0123456789012345", response.text)
        response = await self.create({"PlatformId": 2, "PlatformType": "PAY_LATER", "HasFixedBillDate": False, "AccountNumber": "0123456789012345"})
        self.assertEqual(response.status_code, 422)

    async def test_authentication_and_ownership_are_enforced(self):
        for path in ("/billing/platforms", "/billing/accounts"):
            self.assertEqual((await self.client.get(path)).status_code, 401)
        self.assertEqual((await self.client.post("/billing/accounts", json=self.card())).status_code, 401)
        created = (await self.create(self.card())).json()
        other = self.auth_headers(self.other_id)
        self.assertEqual((await self.client.get("/billing/accounts", headers=other)).json(), [])
        self.assertEqual((await self.client.get("/billing/accounts/" + created["Id"], headers=other)).status_code, 404)

    async def test_missing_or_wrong_encryption_key_is_handled(self):
        with patch.dict(os.environ, {"ENCRYPTION_KEY": ""}):
            self.assertEqual((await self.create(self.card())).status_code, 503)
        async with self.sessions() as db:
            self.assertIsNone(await db.scalar(select(BillingAccount)))
        await self.create(self.card())
        with patch.dict(os.environ, {"ENCRYPTION_KEY": "cd" * 32}):
            self.assertEqual((await self.client.get("/billing/accounts", headers=self.headers)).status_code, 503)
