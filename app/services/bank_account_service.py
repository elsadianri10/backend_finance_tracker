from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, func
from app.models.bank_account_model import BankAccount
from app.models.billing_model import WalletProvider
from app.helpers.bank_encryption import encrypt, masked


async def platforms(db):
    rows = (await db.scalars(select(WalletProvider).where(WalletProvider.is_active.is_(True), WalletProvider.bank_f == 1).order_by(func.lower(WalletProvider.name), WalletProvider.id))).all()
    return [{"Id": p.id, "Name": p.name, "BankF": p.bank_f} for p in rows]


def response(account, name):
    return {"Id": account.id, "PlatformId": account.platform_id, "PlatformName": name,
            "AccountNumberMasked": masked(account.account_number_encrypted, account.id, account.user_id, "account"),
            "CardNumberMasked": masked(account.card_number_encrypted, account.id, account.user_id, "card"),
            "ValidThru": account.valid_thru, "AdminFee": int(account.admin_fee), "OthersFee": int(account.others_fee)}


async def owned(account_id, user_id, db, lock=False):
    query = select(BankAccount).where(BankAccount.id == account_id, BankAccount.user_id == user_id)
    account = await db.scalar(query.with_for_update() if lock else query)
    if account is None:
        raise HTTPException(404, "Bank account not found")
    return account


async def provider(platform_id, db, existing=None):
    platform = await db.get(WalletProvider, platform_id)
    if platform is None or (platform_id != existing and (not platform.is_active or platform.bank_f != 1)):
        raise HTTPException(422, [{"loc": ["body", "PlatformId"], "msg": "Choose an active bank provider", "type": "value_error"}])
    return platform


async def create(payload, user_id, db):
    platform = await provider(payload.platform_id, db)
    account_id = uuid4()
    account = BankAccount(id=account_id, user_id=user_id, platform_id=payload.platform_id,
        account_number_encrypted=encrypt(payload.account_number, account_id, user_id, "account"),
        card_number_encrypted=encrypt(payload.card_number, account_id, user_id, "card"),
        valid_thru=payload.valid_thru, admin_fee=payload.admin_fee, others_fee=payload.others_fee)
    result = response(account, platform.name)
    db.add(account)
    await db.commit()
    return result


async def list_accounts(user_id, db):
    rows = (await db.execute(select(BankAccount, WalletProvider.name).join(WalletProvider, WalletProvider.id == BankAccount.platform_id).where(BankAccount.user_id == user_id).order_by(func.lower(WalletProvider.name), BankAccount.created_at, BankAccount.id))).all()
    return [response(a, name) for a, name in rows]


async def detail(account_id, user_id, db):
    account = await owned(account_id, user_id, db)
    platform = await db.get(WalletProvider, account.platform_id)
    return response(account, platform.name)


async def update(account_id, payload, user_id, db):
    account = await owned(account_id, user_id, db, True)
    platform = await provider(payload.platform_id, db, account.platform_id)
    for field in ("account_number", "card_number"):
        if field in payload.model_fields_set:
            setattr(account, field + "_encrypted", encrypt(getattr(payload, field), account.id, user_id, "account" if field == "account_number" else "card"))
    account.platform_id = payload.platform_id
    account.valid_thru = payload.valid_thru
    account.admin_fee = payload.admin_fee
    account.others_fee = payload.others_fee
    result = response(account, platform.name)
    await db.commit()
    return result


async def delete(account_id, user_id, db):
    account = await owned(account_id, user_id, db, True)
    await db.delete(account)
    await db.commit()
