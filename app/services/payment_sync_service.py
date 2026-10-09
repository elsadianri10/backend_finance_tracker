"""One ledger entry per real payment, shared by all entry points.

Payment mutations serialize on the owner before locking parent records.
Helpers never commit: payment, linked progress, and ledger commit together.
"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4, uuid5, NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select
from app.models.user_model import User
from app.models.routine_model import RoutinePlan, RoutinePayment, LedgerTransaction


async def lock_owner(user_id, db):
    await db.scalar(select(User.id).where(User.id == user_id).with_for_update())


def local_date(stamp):
    return stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).astimezone(timezone(timedelta(hours=7))).date()


async def attach_routine(row, user_id, db, plan=None, request_id=None, billing_transaction_id=None, debt_id=None):
    from app.services.routine_service import active_payments, add_months
    if row.routine_payment_id:
        return row
    if plan is None:
        query = select(RoutinePlan).where(RoutinePlan.user_id == user_id, RoutinePlan.status == 'ACTIVE')
        if billing_transaction_id:
            query = query.where(RoutinePlan.billing_transaction_id == billing_transaction_id)
        elif debt_id:
            query = query.where(RoutinePlan.debt_id == debt_id)
        else:
            return row
        candidates = list(await db.scalars(query.order_by(RoutinePlan.id).with_for_update()))
        eligible = []
        for candidate in candidates:
            paid = await active_payments(candidate.id, db)
            if not candidate.total_cycles or candidate.initial_paid + len(paid) < candidate.total_cycles:
                eligible.append(candidate)
        if len(eligible) > 1:
            raise HTTPException(409, 'Lebih dari satu rencana aktif terhubung; pilih satu rencana aktif')
        plan = eligible[0] if eligible else None
    if plan is None:
        return row
    paid = await active_payments(plan.id, db)
    sequence = plan.initial_paid + len(paid) + 1
    if plan.status != 'ACTIVE' or (plan.total_cycles and sequence > plan.total_cycles):
        raise HTTPException(409, 'Rencana tidak aktif atau selesai')
    payment = RoutinePayment(id=uuid4(), plan_id=plan.id,
        request_id=request_id or uuid5(NAMESPACE_URL, 'ledger:' + str(row.id)),
        sequence=sequence, due_date=add_months(plan.first_due_date, len(paid) * plan.interval_months))
    db.add(payment)
    await db.flush()
    row.routine_payment_id = payment.id
    plan.version += 1
    await db.flush()
    return row


async def billing_ledger(item, bill, user_id, db, bank_id=None, notes='', plan=None, request_id=None):
    from app.services.routine_service import bank_label, invalid
    if int(bill.amount) != bill.amount or int(bill.amount) <= 0:
        invalid('Nominal Tagihan harus rupiah bulat lebih dari 0')
    row = await db.scalar(select(LedgerTransaction).where(
        LedgerTransaction.billing_installment_id == bill.id, LedgerTransaction.voided_at.is_(None)))
    if row is None:
        row = LedgerTransaction(id=uuid4(), user_id=user_id, kind='expense',
            category='debt' if item.tenor else 'bills',
            description=(item.description[:270] + ' · pembayaran ke-' + str(bill.sequence)),
            amount=int(bill.amount), transaction_date=local_date(bill.paid_at),
            source_bank_id=bank_id, source_label=await bank_label(bank_id, user_id, db),
            destination_label='', notes=notes, billing_installment_id=bill.id)
        db.add(row)
        await db.flush()
    return await attach_routine(row, user_id, db, plan, request_id, billing_transaction_id=item.id)


async def debt_ledger(item, payment, user_id, db, bank_id=None, plan=None, request_id=None):
    from app.services.routine_service import bank_label
    row = await db.scalar(select(LedgerTransaction).where(LedgerTransaction.debt_payment_id == payment.id))
    if row is None:
        receivable = item.kind == 'RECEIVABLE'
        row = LedgerTransaction(id=uuid4(), user_id=user_id, kind='income' if receivable else 'expense',
            category='receivable' if receivable else 'debt',
            description=('Terima piutang · ' if receivable else 'Bayar hutang · ') + item.person_name,
            amount=int(payment.amount), transaction_date=payment.payment_date,
            source_bank_id=None if receivable else bank_id,
            destination_bank_id=bank_id if receivable else None,
            source_label='' if receivable else await bank_label(bank_id, user_id, db),
            destination_label=await bank_label(bank_id, user_id, db) if receivable else '',
            notes=payment.notes, debt_payment_id=payment.id)
        db.add(row)
        await db.flush()
    return await attach_routine(row, user_id, db, plan, request_id, debt_id=item.id)
