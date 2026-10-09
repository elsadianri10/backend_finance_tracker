from calendar import monthrange
from datetime import date, datetime, timezone, timedelta
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.billing_model import BillingAccount
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from app.schemas.billing_transaction_schema import TransactionCreate


def month_date(first: date, offset: int, day: int) -> date:
    month = first.year * 12 + first.month - 1 + offset
    year, month = divmod(month, 12)
    return date(year, month + 1, min(day, monthrange(year, month + 1)[1]))


async def owned_account(account_id: UUID, user_id: UUID, db: AsyncSession):
    account = await db.scalar(select(BillingAccount).where(BillingAccount.id == account_id, BillingAccount.user_id == user_id).with_for_update())
    if account is None:
        raise HTTPException(404, "Billing account not found")
    return account


async def owned_transaction(transaction_id: UUID, user_id: UUID, db: AsyncSession, lock=False):
    query = select(BillingTransaction).join(BillingAccount).where(BillingTransaction.id == transaction_id, BillingAccount.user_id == user_id)
    if lock:
        account_id = await db.scalar(select(BillingTransaction.account_id).join(BillingAccount).where(BillingTransaction.id == transaction_id, BillingAccount.user_id == user_id))
        if account_id is None:
            raise HTTPException(404, "Transaction not found")
        await owned_account(account_id, user_id, db)
        # All installment mutations lock the parent row: concurrent clicks cannot skip order.
        query = query.with_for_update(of=BillingTransaction)
    item = await db.scalar(query)
    if item is None:
        raise HTTPException(404, "Transaction not found")
    return item


def local_today():
    return datetime.now(timezone(timedelta(hours=7))).date()


def subscription_due(item, charge):
    if item.recurring_billing_day is None:
        return charge
    issue_offset = 1 if charge.day > item.recurring_billing_day else 0
    due_offset = issue_offset + (1 if item.recurring_due_day <= item.recurring_billing_day else 0)
    return month_date(charge, due_offset, item.recurring_due_day)


async def generate_subscription(item, db):
    if item.transaction_kind != 'SUBSCRIPTION':
        return
    through = min(local_today(), item.stopped_on) if item.stopped_on else local_today()
    latest = await db.scalar(select(BillingInstallment.sequence).where(BillingInstallment.transaction_id == item.id).order_by(BillingInstallment.sequence.desc()).limit(1)) or 0
    offset = latest
    while True:
        anchor = item.transaction_date or item.first_installment
        charge = month_date(anchor, offset, anchor.day)
        if charge > through:
            break
        db.add(BillingInstallment(transaction_id=item.id, sequence=offset + 1, amount=item.amount,
                                 charged_on=charge, due_date=subscription_due(item, charge)))
        offset += 1
    await db.flush()


async def response(item, db):
    bills = (await db.scalars(select(BillingInstallment).where(BillingInstallment.transaction_id == item.id).order_by(BillingInstallment.sequence))).all()
    next_charge = None
    if item.transaction_kind == 'SUBSCRIPTION' and item.stopped_on is None:
        anchor = item.transaction_date or item.first_installment
        next_charge = month_date(anchor, len(bills), anchor.day)
    return {"Id": item.id, "AccountId": item.account_id, "Description": item.description, "Tenor": item.tenor,
            "TransactionDate": item.transaction_date, "FirstInstallment": item.first_installment, "LastInstallment": item.last_installment,
            "TransactionKind": item.transaction_kind, "StoppedOn": item.stopped_on,
            "NextChargeDate": next_charge, "NextDueDate": subscription_due(item, next_charge) if next_charge else None,
            "Amount": int(item.amount), "Notes": item.notes,
            "Installments": [{"Id": bill.id, "Sequence": bill.sequence, "Amount": int(bill.amount), "DueDate": bill.due_date,
                              "ChargedOn": bill.charged_on, "PaidAt": bill.paid_at} for bill in bills]}


async def create(account_id, payload: TransactionCreate, user_id, db):
    account = await owned_account(account_id, user_id, db)
    subscription = payload.transaction_kind == 'SUBSCRIPTION'
    count = payload.tenor or 1
    if payload.transaction_date is not None:
        transaction_date = payload.transaction_date
        if account.has_fixed_bill_date:
            offset = 1 if transaction_date.day > account.billing_date else 0
            first = month_date(transaction_date, offset, account.billing_date)
            due_offset = 1 if account.due_date <= account.billing_date else 0
            due_first = month_date(first, due_offset, account.due_date)
            day = account.due_date
            last = month_date(due_first, count - 1, day)
        else:
            first = due_first = transaction_date
            day = transaction_date.day
            last = month_date(transaction_date, count - 1, day)
        for field, submitted, expected in [('FirstInstallment', payload.first_installment, first), ('LastInstallment', payload.last_installment, last)]:
            if submitted is not None and submitted != expected:
                raise HTTPException(422, [{"loc": ["body", field], "msg": "Date must match TransactionDate and account billing schedule", "type": "value_error"}])
    else:
        # Historical clients and existing schedules retain their original date semantics.
        first = payload.first_installment
        last = month_date(first, count - 1, first.day)
        if not subscription and (payload.last_installment.year, payload.last_installment.month) != (last.year, last.month):
            raise HTTPException(422, [{"loc": ["body", "LastInstallment"], "msg": "Last month must match the selected tenor", "type": "value_error"}])
        day = account.due_date if account.has_fixed_bill_date else first.day
        due_first = month_date(first, 0, day)
    item = BillingTransaction(account_id=account_id, description=payload.description, tenor=payload.tenor,
                              transaction_kind=payload.transaction_kind, transaction_date=payload.transaction_date,
                              first_installment=first, last_installment=None if subscription else last,
                              amount=payload.amount, notes=payload.notes,
                              recurring_billing_day=account.billing_date if subscription and account.has_fixed_bill_date else None,
                              recurring_due_day=account.due_date if subscription and account.has_fixed_bill_date else None)
    db.add(item)
    await db.flush()
    if subscription:
        await generate_subscription(item, db)
    else:
        db.add_all([BillingInstallment(transaction_id=item.id, sequence=i + 1, amount=payload.amount,
                                      due_date=month_date(due_first, i, day)) for i in range(count)])
        await db.flush()
    result = await response(item, db)
    await db.commit()
    return result


async def list_transactions(account_id, user_id, db):
    await owned_account(account_id, user_id, db)
    items = (await db.scalars(select(BillingTransaction).where(BillingTransaction.account_id == account_id).order_by(BillingTransaction.created_at.desc(), BillingTransaction.id).with_for_update())).all()
    for item in items:
        await generate_subscription(item, db)
    result = [await response(item, db) for item in items]
    await db.commit()
    return result


async def detail(transaction_id, user_id, db):
    item = await owned_transaction(transaction_id, user_id, db, lock=True)
    await generate_subscription(item, db)
    result = await response(item, db)
    await db.commit()
    return result


async def mark_paid(transaction_id, installment_id, user_id, db, commit=True, sync=True, bank_id=None, notes=''):
    from app.services.payment_sync_service import lock_owner, billing_ledger
    await lock_owner(user_id, db)
    item = await owned_transaction(transaction_id, user_id, db, lock=True)
    await generate_subscription(item, db)
    next_bill = await db.scalar(select(BillingInstallment).where(BillingInstallment.transaction_id == item.id, BillingInstallment.paid_at.is_(None)).order_by(BillingInstallment.sequence).limit(1))
    if next_bill is None or next_bill.id != installment_id:
        raise HTTPException(409, "Only the next unpaid installment can be paid")
    next_bill.paid_at = datetime.now(timezone.utc)
    await db.flush()
    if sync:
        await billing_ledger(item, next_bill, user_id, db, bank_id, notes)
    result = await response(item, db)
    if commit:
        await db.commit()
    return result


async def update_last(transaction_id, amount, user_id, db):
    item = await owned_transaction(transaction_id, user_id, db, lock=True)
    if item.transaction_kind == 'SUBSCRIPTION':
        raise HTTPException(409, "Use subscription amount to change future bills")
    last = await db.scalar(select(BillingInstallment).where(BillingInstallment.transaction_id == item.id).order_by(BillingInstallment.sequence.desc()).limit(1))
    if last is None or last.paid_at is not None:
        raise HTTPException(409, "A paid installment cannot be changed")
    last.amount = amount
    await db.flush()
    result = await response(item, db)
    await db.commit()
    return result


async def update_subscription(transaction_id, amount, user_id, db):
    item = await owned_transaction(transaction_id, user_id, db, lock=True)
    if item.transaction_kind != 'SUBSCRIPTION' or item.stopped_on is not None:
        raise HTTPException(409, "Only an active subscription can be changed")
    await generate_subscription(item, db)
    item.amount = amount
    await db.flush()
    result = await response(item, db)
    await db.commit()
    return result


async def stop_subscription(transaction_id, user_id, db):
    item = await owned_transaction(transaction_id, user_id, db, lock=True)
    if item.transaction_kind != 'SUBSCRIPTION':
        raise HTTPException(409, "Transaction is not a subscription")
    if item.stopped_on is None:
        await generate_subscription(item, db)
        item.stopped_on = local_today()
        await db.flush()
    result = await response(item, db)
    await db.commit()
    return result


async def delete_subscription(transaction_id, user_id, db):
    item = await owned_transaction(transaction_id, user_id, db, lock=True)
    if item.transaction_kind != 'SUBSCRIPTION' or item.stopped_on is None:
        raise HTTPException(409, "Only a stopped subscription can be deleted")
    unpaid = await db.scalar(select(BillingInstallment.id).where(BillingInstallment.transaction_id == item.id, BillingInstallment.paid_at.is_(None)).limit(1))
    if unpaid is not None:
        raise HTTPException(409, "Subscription has unpaid bills")
    await db.execute(delete(BillingInstallment).where(BillingInstallment.transaction_id == item.id))
    await db.execute(delete(BillingTransaction).where(BillingTransaction.id == item.id))
    await db.commit()
