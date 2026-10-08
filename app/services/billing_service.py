from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_model import BillingAccount, BillingPlatform
from app.schemas.billing_schema import BillingAccountCreate, BillingAccountUpdate
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from app.helpers.billing_encryption import encrypt_account_number, masked_account_number


async def list_platforms(db: AsyncSession) -> list[dict]:
    platforms = (await db.scalars(
        select(BillingPlatform).where(BillingPlatform.is_active.is_(True)).order_by(BillingPlatform.bank_f.desc(), func.lower(BillingPlatform.name), BillingPlatform.id)
    )).all()
    return [{"Id": platform.id, "Name": platform.name, "BankF": platform.bank_f,
             "SupportedTypes": ["CREDIT_CARD", "PAY_LATER"]} for platform in platforms]


def account_response(account: BillingAccount, platform_name: str, has_transactions=False, can_delete=True) -> dict:
    masked = None
    if account.account_number_encrypted:
        masked = masked_account_number(account.account_number_encrypted, account.id, account.user_id)
    return {
        "Id": account.id, "PlatformId": account.platform_id,
        "PlatformName": platform_name, "PlatformType": account.platform_type,
        "AccountType": account.account_type, "AccountNumberMasked": masked,
        "ValidThru": account.valid_thru, "HasFixedBillDate": account.has_fixed_bill_date,
        "BillingDate": account.billing_date, "DueDate": account.due_date,
        "HasTransactions": has_transactions, "CanDelete": can_delete,
    }


async def create_account(payload: BillingAccountCreate, user_id: UUID, db: AsyncSession) -> dict:
    platform = await db.get(BillingPlatform, payload.platform_id)
    if platform is None or not platform.is_active:
        raise HTTPException(422, "Platform is unavailable")
    account_id = uuid4()
    encrypted = None
    if payload.account_number is not None:
        encrypted = encrypt_account_number(payload.account_number, account_id, user_id)
    account = BillingAccount(
        id=account_id, user_id=user_id, platform_id=payload.platform_id,
        platform_type=payload.platform_type.value, account_type=payload.account_type,
        account_number_encrypted=encrypted, valid_thru=payload.valid_thru,
        has_fixed_bill_date=payload.has_fixed_bill_date,
        billing_date=payload.billing_date, due_date=payload.due_date,
    )
    db.add(account)
    # Prepare the masked response before committing so an encryption failure cannot
    # leave a saved account behind with a failed API response.
    result = account_response(account, platform.name)
    await db.commit()
    return result


async def list_accounts(user_id: UUID, db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(BillingAccount, BillingPlatform.name)
        .join(BillingPlatform, BillingAccount.platform_id == BillingPlatform.id)
        .where(BillingAccount.user_id == user_id)
        .order_by(BillingAccount.created_at.desc(), BillingAccount.id)
    )).all()
    flags = await account_flags([account.id for account, _ in rows], db)
    return [account_response(account, name, *flags.get(account.id, (False, True))) for account, name in rows]


async def get_account(account_id: UUID, user_id: UUID, db: AsyncSession) -> dict:
    row = (await db.execute(
        select(BillingAccount, BillingPlatform.name)
        .join(BillingPlatform, BillingAccount.platform_id == BillingPlatform.id)
        .where(BillingAccount.id == account_id, BillingAccount.user_id == user_id)
    )).first()
    if row is None:
        raise HTTPException(404, "Billing account not found")
    flags = await account_flags([account_id], db)
    return account_response(*row, *flags.get(account_id, (False, True)))


async def account_flags(account_ids, db):
    if not account_ids:
        return {}
    transactions = (await db.execute(select(BillingTransaction.account_id, func.count(BillingTransaction.id)).where(BillingTransaction.account_id.in_(account_ids)).group_by(BillingTransaction.account_id))).all()
    unpaid = set((await db.scalars(select(BillingTransaction.account_id).join(BillingInstallment).where(BillingTransaction.account_id.in_(account_ids), BillingInstallment.paid_at.is_(None)).distinct())).all())
    unpaid.update((await db.scalars(select(BillingTransaction.account_id).where(BillingTransaction.account_id.in_(account_ids), BillingTransaction.transaction_kind == 'SUBSCRIPTION', BillingTransaction.stopped_on.is_(None)))).all())
    return {account_id: (count > 0, account_id not in unpaid) for account_id, count in transactions}


async def locked_account(account_id, user_id, db):
    account = await db.scalar(select(BillingAccount).where(BillingAccount.id == account_id, BillingAccount.user_id == user_id).with_for_update())
    if account is None:
        raise HTTPException(404, "Billing account not found")
    return account


async def update_account(account_id, payload: BillingAccountUpdate, user_id, db):
    account = await locked_account(account_id, user_id, db)
    flags = (await account_flags([account_id], db)).get(account_id, (False, True))
    changed_platform = (account.platform_id, account.platform_type) != (payload.platform_id, payload.platform_type.value)
    if changed_platform and flags[0]:
        raise HTTPException(409, "Platform cannot change while transactions exist")
    platform = await db.get(BillingPlatform, payload.platform_id)
    if platform is None or (changed_platform and not platform.is_active):
        raise HTTPException(422, "Platform is unavailable")
    encrypted = account.account_number_encrypted
    if payload.platform_type.value == "PAY_LATER":
        encrypted = None
    elif payload.account_number is not None:
        encrypted = encrypt_account_number(payload.account_number, account.id, account.user_id)
    elif changed_platform or encrypted is None:
        raise HTTPException(422, [{"loc": ["body", "AccountNumber"], "msg": "Account number is required for this card", "type": "value_error"}])
    account.platform_id = payload.platform_id
    account.platform_type = payload.platform_type.value
    account.account_type = payload.account_type
    account.account_number_encrypted = encrypted
    account.valid_thru = payload.valid_thru
    account.has_fixed_bill_date = payload.has_fixed_bill_date
    account.billing_date = payload.billing_date
    account.due_date = payload.due_date
    result = account_response(account, platform.name, *flags)
    await db.commit()
    return result


async def delete_account(account_id, user_id, db):
    await locked_account(account_id, user_id, db)
    active_subscription = await db.scalar(select(BillingTransaction.id).where(BillingTransaction.account_id == account_id, BillingTransaction.transaction_kind == 'SUBSCRIPTION', BillingTransaction.stopped_on.is_(None)).limit(1))
    if active_subscription is not None:
        raise HTTPException(409, "Stop active subscriptions before deleting the account")
    # Same account lock used by create_transaction prevents a concurrent new bill.
    transaction_ids = (await db.scalars(select(BillingTransaction.id).where(BillingTransaction.account_id == account_id).order_by(BillingTransaction.id).with_for_update())).all()
    unpaid = await db.scalar(select(BillingInstallment.id).where(BillingInstallment.transaction_id.in_(transaction_ids), BillingInstallment.paid_at.is_(None)).limit(1))
    if unpaid is not None:
        raise HTTPException(409, "Account has unpaid installments")
    await db.execute(delete(BillingInstallment).where(BillingInstallment.transaction_id.in_(transaction_ids)))
    await db.execute(delete(BillingTransaction).where(BillingTransaction.account_id == account_id))
    await db.execute(delete(BillingAccount).where(BillingAccount.id == account_id))
    await db.commit()
