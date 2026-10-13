"""One-use, server-verified WebAuthn ceremonies and hashed recovery codes."""
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4
from typing import NoReturn
import jwt
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from webauthn import (generate_registration_options, generate_authentication_options,
    verify_registration_response, verify_authentication_response, options_to_json, base64url_to_bytes)
from webauthn.helpers.structs import AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor, ResidentKeyRequirement, UserVerificationRequirement
from app.config import auth_settings as settings
from app.models import User, Passkey, PasskeyChallenge, RecoveryCode
from app.services.auth_service import issue_access, token_claims


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def config():
    rp = os.getenv('WEBAUTHN_RP_ID', '').strip()
    origins = [value.strip() for value in os.getenv('WEBAUTHN_ORIGINS', '').split(',') if value.strip()]
    if not rp or not origins:
        raise HTTPException(503, 'Passkey belum dikonfigurasi')
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise HTTPException(503, 'Konfigurasi domain passkey tidak valid')
        host = parsed.hostname or ''
        if (host != rp and not host.endswith('.' + rp)) or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and rp == 'localhost')):
            raise HTTPException(503, 'Konfigurasi domain passkey tidak valid')
    return rp, origins


async def account(token, db, kind='access'):
    claims = token_claims(token, kind)
    user = await db.scalar(select(User).where(User.id == UUID(claims['sub'])).with_for_update())
    if user is None or not user.is_active or claims.get('ver', 0) != user.auth_version:
        raise HTTPException(401, 'Sesi telah berakhir. Silakan login kembali.')
    return user, claims


async def keys(user, db):
    return list(await db.scalars(select(Passkey).where(Passkey.user_id == user.id).order_by(Passkey.created_at, Passkey.id)))


async def fresh(user, claims, db):
    registered = bool(await keys(user, db))
    method = claims.get('auth_method', 'google')
    age = now().timestamp() - claims.get('auth_time', claims['iat'])
    if age > 300 or (registered and method not in ('passkey', 'recovery')):
        if not registered:
            raise HTTPException(403, 'Silakan logout dan login Google kembali sebelum mendaftarkan passkey pertama.')
        raise HTTPException(403, 'Verifikasi passkey kembali sebelum mengubah keamanan akun.')


async def challenge(user, purpose, db):
    await db.execute(delete(PasskeyChallenge).where(PasskeyChallenge.user_id == user.id, PasskeyChallenge.expires_at < now()))
    count = await db.scalar(select(func.count()).select_from(PasskeyChallenge).where(
        PasskeyChallenge.user_id == user.id, PasskeyChallenge.used_at.is_(None)))
    if count >= 10:
        raise HTTPException(429, 'Terlalu banyak permintaan. Tunggu beberapa menit.')
    row = PasskeyChallenge(id=uuid4(), user_id=user.id, purpose=purpose, challenge=secrets.token_bytes(32),
        auth_version=user.auth_version, expires_at=now() + timedelta(minutes=5), attempts=0)
    db.add(row)
    await db.flush()
    return row


async def pending_login(user, db):
    user = await db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active:
        raise HTTPException(403, 'Account is inactive')
    row = await challenge(user, 'LOGIN', db)
    token = jwt.encode({'sub': str(user.id), 'iat': now(), 'exp': row.expires_at,
        'iss': settings.TOKEN_ISSUER, 'aud': settings.TOKEN_AUDIENCE, 'type': 'passkey_pending',
        'jti': str(row.id), 'ver': user.auth_version}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    await db.commit()
    return {'PasskeyRequired': True, 'PendingToken': token, 'ExpiresIn': 300}


async def active_challenge(user, row_id, purpose, db):
    row = await db.scalar(select(PasskeyChallenge).where(PasskeyChallenge.id == row_id,
        PasskeyChallenge.user_id == user.id, PasskeyChallenge.purpose == purpose).with_for_update())
    if row is None or row.used_at or utc(row.expires_at) <= now() or row.attempts >= 5 or row.auth_version != user.auth_version:
        raise HTTPException(401, 'Verifikasi kedaluwarsa. Mulai kembali.')
    return row


async def failed(row, db) -> NoReturn:
    row.attempts += 1
    if row.attempts >= 5:
        row.used_at = now()
    await db.commit()
    raise HTTPException(401, 'Verifikasi tidak berhasil. Coba kembali.')


async def options(token, db, purpose):
    user, claims = await account(token, db, 'passkey_pending' if purpose == 'LOGIN' else 'access')
    rp, _ = config()
    existing = await keys(user, db)
    if purpose == 'REGISTER':
        await fresh(user, claims, db)
        if len(existing) >= 10:
            raise HTTPException(409, 'Maksimal 10 passkey per akun.')
        if any(key.rp_id != rp for key in existing):
            raise HTTPException(409, 'Domain passkey berbeda dari domain akun.')
    row = await active_challenge(user, UUID(claims['jti']), purpose, db) if purpose == 'LOGIN' else await challenge(user, purpose, db)
    descriptors = [PublicKeyCredentialDescriptor(id=key.credential_id) for key in existing if key.rp_id == rp]
    if purpose == 'REGISTER':
        opts = generate_registration_options(rp_id=rp, rp_name='Finance Tracker', user_name=user.email,
            user_id=user.id.bytes, user_display_name=user.name, challenge=row.challenge,
            exclude_credentials=descriptors, authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED))
    else:
        if not descriptors:
            raise HTTPException(409, 'Passkey untuk domain ini tidak tersedia.')
        opts = generate_authentication_options(rp_id=rp, challenge=row.challenge, allow_credentials=descriptors,
            user_verification=UserVerificationRequirement.REQUIRED)
    await db.commit()
    return {'ChallengeId': str(row.id), 'Options': json.loads(options_to_json(opts))}


def code_hash(code):
    return hmac.new(settings.SECRET_KEY.encode(), code.replace('-', '').replace(' ', '').upper().encode(), hashlib.sha256).hexdigest()


async def new_codes(user, db):
    for old in await db.scalars(select(RecoveryCode).where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))):
        old.used_at = now()
    codes = []
    for _ in range(8):
        raw = secrets.token_hex(16).upper()
        code = '-'.join(raw[i:i+8] for i in range(0, 32, 8))
        db.add(RecoveryCode(user_id=user.id, code_hash=code_hash(code)))
        codes.append(code)
    return codes


async def verify(token, payload, db, purpose):
    user, claims = await account(token, db, 'passkey_pending' if purpose == 'LOGIN' else 'access')
    if purpose == 'LOGIN' and str(payload.challenge_id) != claims.get('jti'):
        raise HTTPException(401, 'Verifikasi tidak sesuai sesi login.')
    row = await active_challenge(user, payload.challenge_id, purpose, db)
    rp, origins = config()
    codes = []
    if purpose == 'REGISTER':
        await fresh(user, claims, db)
        existing = await keys(user, db)
        if len(existing) >= 10:
            raise HTTPException(409, 'Maksimal 10 passkey per akun.')
        try:
            verified = verify_registration_response(credential=payload.credential, expected_challenge=row.challenge,
                expected_rp_id=rp, expected_origin=origins, require_user_verification=True)
        except Exception:
            await failed(row, db)
        db.add(Passkey(user_id=user.id, credential_id=verified.credential_id, public_key=verified.credential_public_key,
            name=payload.name.strip() or 'Passkey', rp_id=rp, sign_count=verified.sign_count,
            backed_up=verified.credential_backed_up))
        user.auth_version += 1
        if not existing:
            codes = await new_codes(user, db)
    else:
        try:
            credential_id = base64url_to_bytes(payload.credential['id'])
            key = await db.scalar(select(Passkey).where(Passkey.user_id == user.id,
                Passkey.credential_id == credential_id, Passkey.rp_id == rp).with_for_update())
            if key is None:
                raise ValueError('Unknown credential')
            response = payload.credential.get('response', {})
            if response.get('userHandle') and base64url_to_bytes(response['userHandle']) != user.id.bytes:
                raise ValueError('Wrong user handle')
            verified_auth = verify_authentication_response(credential=payload.credential, expected_challenge=row.challenge,
                expected_rp_id=rp, expected_origin=origins, credential_public_key=key.public_key,
                credential_current_sign_count=key.sign_count, require_user_verification=True)
        except Exception:
            await failed(row, db)
        key.sign_count = verified_auth.new_sign_count
        key.backed_up = verified_auth.credential_backed_up
        key.last_used_at = now()
    row.used_at = now()
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, 'Passkey sudah terdaftar.')
    return issue_access(user, 'passkey') | {'RecoveryCodes': codes}


async def recover(token, code, db):
    user, claims = await account(token, db, 'passkey_pending')
    challenge_row = await active_challenge(user, UUID(claims['jti']), 'LOGIN', db)
    row = await db.scalar(select(RecoveryCode).where(RecoveryCode.user_id == user.id,
        RecoveryCode.code_hash == code_hash(code), RecoveryCode.used_at.is_(None)).with_for_update())
    if row is None:
        await failed(challenge_row, db)
    row.used_at = now()
    challenge_row.used_at = now()
    user.auth_version += 1
    await db.commit()
    return issue_access(user, 'recovery')


async def state(token, db):
    user, _ = await account(token, db)
    registered = await keys(user, db)
    count = await db.scalar(select(func.count()).select_from(RecoveryCode).where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)))
    return {'Enabled': bool(registered), 'RecoveryRemaining': count, 'Passkeys': [
        {'Id': str(key.id), 'Name': key.name, 'CreatedAt': key.created_at,
         'LastUsedAt': key.last_used_at, 'BackedUp': key.backed_up} for key in registered]}


async def remove(token, key_id, db):
    user, claims = await account(token, db)
    await fresh(user, claims, db)
    existing = await keys(user, db)
    key = next((key for key in existing if key.id == key_id), None)
    if key is None:
        raise HTTPException(404, 'Passkey tidak ditemukan.')
    if len(existing) <= 1:
        raise HTTPException(409, 'Tambahkan passkey pengganti sebelum menghapus passkey terakhir.')
    await db.delete(key)
    user.auth_version += 1
    await db.commit()
    return issue_access(user, claims.get('auth_method', 'passkey'))


async def regenerate(token, db):
    user, claims = await account(token, db)
    await fresh(user, claims, db)
    if not await keys(user, db):
        raise HTTPException(409, 'Daftarkan passkey terlebih dahulu.')
    codes = await new_codes(user, db)
    user.auth_version += 1
    await db.commit()
    return issue_access(user, claims.get('auth_method', 'passkey')) | {'RecoveryCodes': codes}
