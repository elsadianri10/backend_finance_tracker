"""Account entitlements; admin authority is separate from Pro access."""
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import overload
from fastapi import HTTPException
from sqlalchemy import select, func, or_
from app.models.user_model import User
from app.models.access_model import AccountAccess, AccessAudit
from app.config.admin_settings import is_owner_email


TRIAL_DAYS = 30


def now():
    return datetime.now(timezone.utc)


@overload
def utc(value: datetime) -> datetime: ...


@overload
def utc(value: None) -> None: ...


def utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=value.tzinfo or timezone.utc) if value else None


def is_admin(user):
    return bool(user and user.is_active and user.admin_f == 1)


def require_admin(user):
    if not is_admin(user):
        raise HTTPException(403, 'Hanya admin yang dapat mengelola akses')


async def start_trial(user, db, at=None):
    """Initialize once on verified Google registration/login, serialized per account."""
    await db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    row = await db.get(AccountAccess, user.id)
    if row is None:
        row = AccountAccess(user_id=user.id, version=1)
        db.add(row)
    if row.trial_started_at is None:
        row.trial_started_at = at or now()
        row.trial_until = row.trial_started_at + timedelta(days=TRIAL_DAYS)
        # An existing grant may have an admin editor open. Preserve its version check.
        if row not in db.new:
            row.version += 1
    await db.flush()
    return row


def status(row, at=None):
    at = at or now()
    started = utc(row.trial_started_at) if row else None
    trial_end = utc(row.trial_until) if row else None
    trial = bool(started and trial_end and started <= at < trial_end)
    expired = bool(trial_end and trial_end <= at)
    gift = bool(row and row.complimentary and (row.complimentary_until is None or utc(row.complimentary_until) > at))
    paid = bool(row and row.subscription_plan == 'PRO' and row.subscription_until and utc(row.subscription_until) > at)
    return {'EffectivePlan': 'PRO' if gift or paid or trial else 'FREE',
            'Source': 'COMPLIMENTARY' if gift else 'SUBSCRIPTION' if paid else 'TRIAL' if trial else 'FREE',
            'ExpiresAt': utc(row.complimentary_until) if gift else utc(row.subscription_until) if paid else trial_end if trial else None,
            'TrialStartedAt': started, 'TrialEndsAt': trial_end, 'TrialActive': trial, 'TrialExpired': expired,
            'TrialDaysRemaining': max(0, ceil((trial_end - at).total_seconds() / 86400)) if trial_end else 0,
            'Complimentary': bool(row and row.complimentary),
            'ComplimentaryUntil': utc(row.complimentary_until) if row else None,
            'SubscriptionPlan': row.subscription_plan if row else 'FREE',
            'SubscriptionUntil': utc(row.subscription_until) if row else None,
            'Version': row.version if row else 0}


async def mine(user, db):
    return status(await db.get(AccountAccess, user.id)) | {'IsAdmin': is_admin(user)}


async def users(user, db, search='', offset=0, limit=25):
    require_admin(user)
    predicate = or_(User.email.icontains(search.strip(), autoescape=True), User.name.icontains(search.strip(), autoescape=True))
    total = await db.scalar(select(func.count()).select_from(User).where(predicate))
    rows = (await db.execute(select(User, AccountAccess).outerjoin(AccountAccess, AccountAccess.user_id == User.id)
        .where(predicate).order_by(User.email, User.id).offset(offset).limit(limit))).all()
    return {'Items': [{'Id': target.id, 'Email': target.email, 'Name': target.name, 'Active': target.is_active, 'AdminF': target.admin_f, 'OwnerAdmin': is_owner_email(target.email),
                      'Access': status(access)} for target, access in rows], 'Total': total,
            'NextOffset': offset + limit if offset + limit < total else None}


async def change(target_id, payload, user, db):
    require_admin(user)
    target = await db.scalar(select(User).where(User.id == target_id).with_for_update())
    if target is None:
        raise HTTPException(404, 'Akun tidak ditemukan')
    if payload.action == 'GRANT' and not target.is_active:
        raise HTTPException(409, 'Akun nonaktif tidak dapat diberi akses')
    row = await db.get(AccountAccess, target.id)
    if payload.version != (row.version if row else 0):
        raise HTTPException(409, 'Pengaturan sudah berubah. Muat ulang sebelum menyimpan.')
    if payload.expires_at and payload.expires_at <= now():
        raise HTTPException(422, 'Tanggal berakhir harus di masa depan')
    if row is None:
        row = AccountAccess(user_id=target.id, version=0)
        db.add(row)
    row.complimentary = payload.action == 'GRANT'
    row.complimentary_until = payload.expires_at if row.complimentary else None
    row.version += 1
    db.add(AccessAudit(user_id=target.id, actor_id=user.id, action=payload.action,
                       expires_at=row.complimentary_until, reason=payload.reason))
    await db.commit()
    return {'Id': target.id, 'Email': target.email, 'Name': target.name, 'Active': target.is_active, 'AdminF': target.admin_f, 'OwnerAdmin': is_owner_email(target.email), 'Access': status(row)}


async def history(target_id, user, db):
    require_admin(user)
    rows = (await db.execute(select(AccessAudit, User.email).outerjoin(User, AccessAudit.actor_id == User.id)
        .where(AccessAudit.user_id == target_id).order_by(AccessAudit.created_at.desc(), AccessAudit.id.desc()).limit(30))).all()
    return [{'Id': row.id, 'Action': row.action, 'ExpiresAt': utc(row.expires_at), 'Reason': row.reason,
             'CreatedAt': utc(row.created_at), 'ActorEmail': email} for row, email in rows]


async def require_pro(user_id, db):
    if status(await db.get(AccountAccess, user_id))['EffectivePlan'] != 'PRO':
        raise HTTPException(403, 'PRO_REQUIRED')
