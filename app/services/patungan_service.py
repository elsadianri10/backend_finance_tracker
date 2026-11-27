from calendar import monthrange
from collections import defaultdict
from datetime import date
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models.patungan_model import SharedSubscription, SubscriptionMember, SubscriptionReceipt, SubscriptionWaiver
from app.models.routine_model import LedgerTransaction
from app.services.billing_transaction_service import local_today
from app.services.payment_sync_service import lock_owner


def month_start(value):
    return value.replace(day=1)


def next_month(value):
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def group_output(group):
    return {'Id': group.id, 'Name': group.name, 'MonthlyAmount': group.monthly_amount,
            'ClosedOn': group.closed_on}


def member_output(member):
    return {'Id': member.id, 'Name': member.name, 'JoinedOn': member.joined_on,
            'LeftOn': member.left_on, 'PayAtYearEnd': member.pay_at_year_end, 'Version': member.version}


def calendar_output(member, group, waivers, receipts, year, today):
    last = date(year, 12, 1)
    rate = group.monthly_amount
    joined = month_start(member.joined_on)
    left = month_start(member.left_on) if member.left_on else None
    closed = month_start(group.closed_on) if group.closed_on else None
    months = {}
    month = joined
    last_billable = min(last, left or last, closed or last)
    while month <= last_billable:
        if month not in waivers:
            months[month] = 0
        month = next_month(month)

    credit = 0
    # Reserve deliberately targeted months before applying general payments.
    for receipt in sorted(receipts, key=lambda row: row.start_month is None):
        remaining = receipt.amount
        for month, paid in months.items():
            if receipt.start_month and month < receipt.start_month:
                continue
            applied = min(rate - paid, remaining)
            months[month] += applied
            remaining -= applied
            if not remaining:
                break
        credit += remaining

    rows = []
    for number in range(1, 13):
        month = date(year, number, 1)
        paid, amount = months.get(month, 0), 0
        due = None
        if closed and month > closed:
            status = 'CLOSED'
        elif month < joined:
            status = 'NOT_JOINED'
        elif left and month > left:
            status = 'LEFT'
        elif month in waivers:
            status = 'WAIVED'
        else:
            amount = rate
            due = date(year, 12, 31) if member.pay_at_year_end else date(year, number, monthrange(year, number)[1])
            if paid == rate:
                status = 'PAID'
            elif paid:
                status = 'PARTIAL'
            elif month > month_start(today):
                status = 'UPCOMING'
            elif today > due:
                status = 'OVERDUE'
            elif member.pay_at_year_end:
                status = 'SCHEDULED'
            else:
                status = 'UNPAID'
        rows.append({'Month': month, 'Status': status, 'Amount': amount, 'Paid': paid, 'DueOn': due,
                     'Overdue': bool(due and today > due and paid < amount)})
    outstanding = sum(row['Amount'] - row['Paid'] for row in rows if row['Month'] <= today)
    history = [{'Id': row.id, 'TransactionId': row.transaction_id, 'PaidOn': row.paid_on,
                'Amount': row.amount, 'StartMonth': row.start_month, 'Notes': row.notes} for row in receipts]
    return member_output(member) | {'Months': rows, 'Credit': credit, 'Outstanding': outstanding, 'Payments': history}


async def groups(user_id, db):
    rows = await db.scalars(select(SharedSubscription).where(SharedSubscription.user_id == user_id)
                            .order_by(SharedSubscription.name, SharedSubscription.id))
    return [group_output(row) for row in rows]


async def owned_group(group_id, user_id, db):
    row = await db.scalar(select(SharedSubscription).where(SharedSubscription.id == group_id,
                                                            SharedSubscription.user_id == user_id))
    if row is None:
        raise HTTPException(404, 'Patungan tidak ditemukan')
    return row


async def owned_member(member_id, user_id, db):
    rows = await db.execute(select(SubscriptionMember, SharedSubscription).join(SharedSubscription)
                            .where(SubscriptionMember.id == member_id, SharedSubscription.user_id == user_id))
    row = rows.one_or_none()
    if row is None:
        raise HTTPException(404, 'Anggota tidak ditemukan')
    member, group = row
    return member, group


async def detail(group_id, year, user_id, db):
    group = await owned_group(group_id, user_id, db)
    members = list(await db.scalars(select(SubscriptionMember).where(SubscriptionMember.subscription_id == group.id)
                                  .order_by(SubscriptionMember.joined_on, SubscriptionMember.name, SubscriptionMember.id)))
    waivers, receipts = defaultdict(set), defaultdict(list)
    ids = [member.id for member in members]
    if ids:
        for row in await db.scalars(select(SubscriptionWaiver).where(SubscriptionWaiver.member_id.in_(ids))):
            waivers[row.member_id].add(row.month)
        for row in await db.scalars(select(SubscriptionReceipt).where(SubscriptionReceipt.member_id.in_(ids))
                                    .order_by(SubscriptionReceipt.paid_on, SubscriptionReceipt.id)):
            receipts[row.member_id].append(row)
    today = local_today()
    return group_output(group) | {'Year': year, 'Members': [
        calendar_output(member, group, waivers[member.id], receipts[member.id], year, today)
        for member in members
    ]}


async def create_group(payload, user_id, db):
    group = SharedSubscription(**payload.model_dump(), user_id=user_id, id=uuid4())
    db.add(group)
    await db.commit()
    return group_output(group)


async def close_group(group_id, payload, user_id, db):
    await lock_owner(user_id, db)
    group = await owned_group(group_id, user_id, db)
    if group.closed_on and group.closed_on != payload.closed_on:
        raise HTTPException(409, 'Patungan sudah ditutup')
    if payload.closed_on > local_today():
        raise HTTPException(422, 'Tanggal tutup maksimal hari ini')
    group.closed_on = payload.closed_on
    result = group_output(group)
    await db.commit()
    return result


async def delete_group(group_id, user_id, db):
    await lock_owner(user_id, db)
    group = await owned_group(group_id, user_id, db)
    await db.delete(group)
    await db.commit()


async def create_member(group_id, payload, user_id, db):
    await lock_owner(user_id, db)
    group = await owned_group(group_id, user_id, db)
    if group.closed_on:
        raise HTTPException(409, 'Patungan sudah ditutup')
    row = SubscriptionMember(subscription_id=group_id, **payload.model_dump())
    db.add(row)
    await db.flush()
    result = member_output(row)
    await db.commit()
    return result


async def update_member(member_id, payload, user_id, db):
    await lock_owner(user_id, db)
    row, group = await owned_member(member_id, user_id, db)
    if row.version != payload.version:
        raise HTTPException(409, 'Data anggota sudah berubah')
    if row.joined_on != payload.joined_on and await db.scalar(
        select(SubscriptionReceipt.id).where(SubscriptionReceipt.member_id == row.id).limit(1)
    ):
        raise HTTPException(409, 'Tanggal masuk terkunci setelah ada pembayaran')
    if group.closed_on and row.joined_on != payload.joined_on and payload.joined_on > group.closed_on:
        raise HTTPException(422, 'Tanggal masuk harus sama atau sebelum tanggal tutup')
    for field, value in payload.model_dump(exclude={'version'}).items():
        setattr(row, field, value)
    row.version += 1
    result = member_output(row)
    await db.commit()
    return result


def within_membership(member, month, closed_on):
    return month >= month_start(member.joined_on) and (
        not member.left_on or month <= month_start(member.left_on)
    ) and (
        not closed_on or month <= month_start(closed_on)
    )


async def set_waiver(member_id, payload, user_id, db):
    await lock_owner(user_id, db)
    member, group = await owned_member(member_id, user_id, db)
    if payload.waived and not within_membership(member, payload.month, group.closed_on):
        raise HTTPException(422, 'Pilih bulan ketika anggota masih ikut')
    row = await db.get(SubscriptionWaiver, (member_id, payload.month))
    if payload.waived and row is None:
        db.add(SubscriptionWaiver(member_id=member_id, month=payload.month))
    elif not payload.waived and row is not None:
        await db.delete(row)
    await db.commit()


def eligible_transactions(user_id):
    ledger = LedgerTransaction
    return select(ledger).where(
        ledger.user_id == user_id, ledger.kind == 'income', ledger.voided_at.is_(None),
        ledger.category.not_in(('cash_withdrawal', 'receivable')), ledger.saving_movement_id.is_(None),
        ledger.debt_payment_id.is_(None), ledger.routine_payment_id.is_(None),
        ledger.billing_installment_id.is_(None), ledger.transaction_date <= local_today(),
    )


async def transactions(month, user_id, db):
    first = date.fromisoformat(month + '-01')
    ledger = LedgerTransaction
    linked = select(SubscriptionReceipt.id).where(SubscriptionReceipt.transaction_id == ledger.id).exists()
    rows = await db.execute(eligible_transactions(user_id).add_columns(linked)
                            .where(ledger.transaction_date >= first, ledger.transaction_date < next_month(first))
                            .order_by(ledger.transaction_date.desc(), ledger.created_at.desc(), ledger.id))
    return [{'Id': row.id, 'Description': row.description, 'Amount': row.amount,
             'Date': row.transaction_date, 'Linked': used} for row, used in rows]


async def create_payment(member_id, payload, user_id, db):
    await lock_owner(user_id, db)
    member, group = await owned_member(member_id, user_id, db)
    prior = await db.get(SubscriptionReceipt, payload.request_id)
    if prior:
        if (prior.member_id, prior.transaction_id, prior.start_month, prior.notes) == (
            member_id, payload.transaction_id, payload.start_month, payload.notes
        ) and (payload.transaction_id or (prior.amount, prior.paid_on) == (payload.amount, payload.paid_on)):
            return
        raise HTTPException(409, 'Permintaan pembayaran sudah dipakai')
    if payload.start_month and not within_membership(member, payload.start_month, group.closed_on):
        raise HTTPException(422, 'Bulan awal alokasi di luar masa keanggotaan')
    amount, paid_on = payload.amount, payload.paid_on
    if payload.transaction_id:
        tx = await db.scalar(eligible_transactions(user_id).where(LedgerTransaction.id == payload.transaction_id)
                             .with_for_update())
        if tx is None:
            raise HTTPException(404, 'Transaksi uang masuk tidak tersedia')
        if await linked_payment(tx.id, db):
            raise HTTPException(409, 'Transaksi sudah ditautkan')
        amount, paid_on = tx.amount, tx.transaction_date
    if amount is None or paid_on is None or paid_on > local_today():
        raise HTTPException(422, 'Masukkan nominal dan tanggal pembayaran sampai hari ini')
    db.add(SubscriptionReceipt(id=payload.request_id, member_id=member_id, transaction_id=payload.transaction_id,
                               amount=amount, paid_on=paid_on, start_month=payload.start_month, notes=payload.notes))
    await db.commit()


async def linked_payment(transaction_id, db):
    return await db.scalar(select(SubscriptionReceipt.id).where(SubscriptionReceipt.transaction_id == transaction_id))


async def detach_payment(member_id, payment_id, user_id, db):
    await lock_owner(user_id, db)
    await owned_member(member_id, user_id, db)
    row = await db.scalar(select(SubscriptionReceipt).where(SubscriptionReceipt.id == payment_id,
                                                              SubscriptionReceipt.member_id == member_id))
    if row is None:
        raise HTTPException(404, 'Pembayaran tidak ditemukan')
    await db.delete(row)
    await db.commit()
