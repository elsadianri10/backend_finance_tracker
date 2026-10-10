from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import auth_settings as settings
from app.models.user_model import User

logger = logging.getLogger(__name__)


def google_rejection_reason(exc: Exception) -> str:
    # Never log the exception text: it can contain claim values or credentials.
    message = str(exc).lower()
    if "audience" in message or "aud claim" in message:
        return "client_id_mismatch"
    if "too early" in message or "not yet valid" in message:
        return "token_not_yet_valid_check_system_clock"
    if "expired" in message:
        return "token_expired"
    if "issuer" in message:
        return "invalid_issuer"
    if "signature" in message:
        return "invalid_signature"
    if "certificate" in message or "certs" in message:
        return "signing_key_unavailable"
    return "invalid_token_format_or_claims"


class GoogleRequest(Request):
    def __call__(self, *args, **kwargs):
        kwargs.setdefault("timeout", 10)
        return super().__call__(*args, **kwargs)


def verify_google_token(token: str) -> Mapping[str, Any]:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Configure GOOGLE_CLIENT_ID")
    try:
        claims = id_token.verify_oauth2_token(
            token,
            GoogleRequest(),
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=60,
        )
    except TransportError as exc:
        logger.warning("Google login rejected: verification_service_unavailable")
        raise HTTPException(503, "Google verification is temporarily unavailable") from exc
    except (ValueError, GoogleAuthError) as exc:
        logger.warning("Google login rejected: %s", google_rejection_reason(exc))
        raise HTTPException(401, "Invalid or expired Google ID token") from exc
    if (
        claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com")
        or claims.get("aud") != settings.GOOGLE_CLIENT_ID
        or claims.get("email_verified") is not True
        or not isinstance(claims.get("sub"), str)
        or not 1 <= len(claims["sub"]) <= 255
        or not isinstance(claims.get("email"), str)
        or not 1 <= len(claims["email"]) <= 320
    ):
        reason = "invalid_identity_claims"
        if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
            reason = "client_id_mismatch"
        elif claims.get("email_verified") is not True:
            reason = "email_not_verified"
        logger.warning("Google login rejected: %s", reason)
        raise HTTPException(401, "Google identity must have a verified email and valid subject")
    return claims


async def google_login(token: str, db: AsyncSession) -> dict:
    settings.require_token_settings()
    claims = await run_in_threadpool(verify_google_token, token)
    user = await db.scalar(select(User).where(User.google_sub == claims["sub"]))
    now = datetime.now(timezone.utc)
    if user is None:
        user = User(google_sub=claims["sub"], email=claims["email"], name="", last_login_at=now)
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:
            # Concurrent first logins must resolve to the same account.
            await db.rollback()
            user = await db.scalar(select(User).where(User.google_sub == claims["sub"]))
            if user is None:
                raise
    if not user.is_active:
        await db.rollback()
        raise HTTPException(403, "Account is inactive")
    user.email = claims["email"]
    user.name = str(claims.get("name") or claims["email"])[:255]
    picture = claims.get("picture")
    user.picture_url = picture[:2048] if isinstance(picture, str) else None
    user.last_login_at = now
    await db.commit()
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    access_token = jwt.encode(
        {
            "sub": str(user.id), "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "iss": settings.TOKEN_ISSUER, "aud": settings.TOKEN_AUDIENCE,
            "type": "access",
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"AccessToken": access_token, "TokenType": "bearer", "ExpiresIn": expires_in, "User": user}


async def user_from_access_token(token: str, db: AsyncSession) -> User:
    settings.require_token_settings()
    unauthorized = HTTPException(401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
            audience=settings.TOKEN_AUDIENCE, issuer=settings.TOKEN_ISSUER,
            options={"require": ["sub", "iat", "exp", "iss", "aud", "type"]},
        )
        if claims["type"] != "access":
            raise unauthorized
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise unauthorized from exc
    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(403, "Account is inactive")
    return user
