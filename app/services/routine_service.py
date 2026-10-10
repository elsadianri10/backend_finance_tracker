import calendar
from datetime import date, datetime, timezone
from typing import Any, NoReturn
from uuid import UUID, uuid4, uuid5
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.routine_model import RoutinePlan, RoutinePayment, LedgerTransaction, TransactionImport
from app.models.user_model import User
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from app.models.billing_model import BillingAccount
from app.models.debt_model import Debt, DebtPayment
from app.services.bank_account_service import detail as bank_detail, list_accounts


def invalid(message) -> NoReturn:
    raise HTTPException(422, [{'loc': ['body'], 'msg': message, 'type': 'value_error'}])


def add_months(value, offset):
    total = value.year * 12 + value.month - 1 + offset
    year, month = divmod(total, 12)
    if year > 9999:
        invalid('Jadwal melampaui batas tanggal')
    return date(year, month + 1, min(value.day, calendar.monthrange(year, month + 1)[1]))


async def owned(model, item_id, user_id, db, lock=False):
    row = await db.scalar(select(model).where(model.id == item_id, model.user_id == user_id).with_for_update() if lock else select(model).where(model.id == item_id, model.user_id == user_id))
    if row is None:
        raise HTTPException(404, 'Record not found')
    return row


async def bank_label(bank_id, user_id, db):
    if bank_id is None:
        return ''
    bank = await bank_detail(bank_id, user_id, db)
    return bank['PlatformName'] + ' · ' + bank['AccountNumberMasked']


def transaction_response(row):
    return {'Id': str(row.id), 'Kind': row.kind, 'Category': row.category, 'Description': row.description,
            'Amount': row.amount, 'TransactionDate': row.transaction_date.isoformat(), 'SourceBankId': str(row.source_bank_id) if row.source_bank_id else None,
            'DestinationBankId': str(row.destination_bank_id) if row.destination_bank_id else None, 'SourceLabel': row.source_label,
            'DestinationLabel': row.destination_label, 'Notes': row.notes, 'RoutinePaymentId': str(row.routine_payment_id) if row.routine_payment_id else None,
            'BillingInstallmentId': str(row.billing_installment_id) if row.billing_installment_id else None,
            'DebtPaymentId': str(row.debt_payment_id) if row.debt_payment_id else None,
            'SavingMovementId': str(row.saving_movement_id) if row.saving_movement_id else None}


async def list_transactions(user_id, db):
    rows = await db.scalars(select(LedgerTransaction).where(LedgerTransaction.user_id == user_id, LedgerTransaction.voided_at.is_(None)).order_by(LedgerTransaction.transaction_date.desc(), LedgerTransaction.created_at.desc(), LedgerTransaction.id))
    return [transaction_response(row) for row in rows]


async def save_transaction(payload, user_id, db, item_id=None):
    from hashlib import sha256
    from app.services.payment_sync_service import lock_owner
    await lock_owner(user_id, db)
    fingerprint = sha256(payload.model_dump_json(exclude={'request_id'}).encode()).hexdigest()
    if not item_id and payload.request_id:
        repeat = await db.scalar(select(LedgerTransaction).where(LedgerTransaction.user_id == user_id, LedgerTransaction.request_id == payload.request_id))
        if repeat:
            if repeat.voided_at or repeat.request_hash != fingerprint:
                raise HTTPException(409, 'Permintaan transaksi telah digunakan')
            return transaction_response(repeat)
    row = await owned(LedgerTransaction, item_id, user_id, db, True) if item_id else LedgerTransaction(id=uuid4(), user_id=user_id)
    linked = payload.debt_id or payload.billing_installment_id or payload.routine_plan_id
    if item_id and (row.routine_payment_id or row.billing_installment_id or row.debt_payment_id or row.saving_movement_id or row.voided_at or linked or payload.saving_id):
        raise HTTPException(409, 'Pembayaran tertaut diubah melalui menu asal')
    source = await bank_label(payload.source_bank_id, user_id, db)
    destination = await bank_label(payload.destination_bank_id, user_id, db)
    if linked:
        row = await linked_transaction(payload, user_id, db)
        row.request_id, row.request_hash = payload.request_id, fingerprint
        await db.flush()
        result = transaction_response(row)
        await db.commit()
        return result
    excluded = {'debt_id','billing_installment_id','routine_plan_id','routine_sequence','saving_id'}
    if item_id:
        excluded.add('request_id')
    for key, value in payload.model_dump(exclude=excluded).items():
        setattr(row, key, value)
    if not item_id:
        row.request_hash = fingerprint
    row.source_label, row.destination_label = source, destination
    db.add(row)
    await db.flush()
    if payload.saving_id:
        from app.services.savings_sync_service import apply_movement
        if not ((payload.kind == 'income' and payload.category == 'cash_withdrawal') or (payload.kind == 'transfer' and payload.category == 'savings')):
            invalid('Savings hanya untuk Tarik Tunai atau Alokasi Tabungan')
        await apply_movement(row, payload.saving_id, 'REMOVE' if payload.category == 'cash_withdrawal' else 'ADD', payload.request_id, user_id, db)
        await db.flush()
    result = transaction_response(row)
    await db.commit()
    return result


async def remove_transaction(item_id, user_id, db):
    row = await owned(LedgerTransaction, item_id, user_id, db, True)
    if row.routine_payment_id or row.billing_installment_id or row.debt_payment_id or row.saving_movement_id:
        raise HTTPException(409, 'Pembayaran tertaut dikelola melalui menu asal')
    row.voided_at = datetime.now(timezone.utc)
    await db.commit()


async def import_transactions(payload, user_id, db):
    # Serialize imports per owner; tombstones + marker prevent deleted rows returning.
    await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if await db.get(TransactionImport, user_id) is None:
        for old in payload.transactions:
            db.add(LedgerTransaction(id=uuid5(user_id, old.id), user_id=user_id, legacy_id=old.id,
                                    kind=old.type, description=old.description, category=old.category, amount=old.amount,
                                    transaction_date=old.transaction_date, source_label='', destination_label='', notes=''))
        db.add(TransactionImport(user_id=user_id))
        await db.commit()
    return {'Imported': True}


async def options(user_id, db):
    from app.services import billing_transaction_service as billing, debt_service
    from app.services.payment_sync_service import lock_owner, local_date
    await lock_owner(user_id, db)
    banks = await list_accounts(user_id, db)
    bills = (await db.execute(select(BillingTransaction, BillingAccount.account_type).join(BillingAccount, BillingTransaction.account_id == BillingAccount.id).where(BillingAccount.user_id == user_id).order_by(BillingTransaction.description))).all()
    subscription_ids = [bill.id for bill, _ in bills if bill.transaction_kind == 'SUBSCRIPTION']
    latest = dict((await db.execute(select(BillingInstallment.transaction_id, func.max(BillingInstallment.sequence))
        .where(BillingInstallment.transaction_id.in_(subscription_ids)).group_by(BillingInstallment.transaction_id))).all()) if subscription_ids else {}
    for bill, label in bills:
        await billing.generate_subscription(bill, db, latest=latest.get(bill.id, 0))
    installments = list(await db.scalars(select(BillingInstallment).join(BillingTransaction, BillingInstallment.transaction_id == BillingTransaction.id).join(BillingAccount, BillingTransaction.account_id == BillingAccount.id).where(BillingAccount.user_id == user_id).order_by(BillingInstallment.sequence)))
    recorded = set(await db.scalars(select(LedgerTransaction.billing_installment_id).where(LedgerTransaction.user_id == user_id, LedgerTransaction.voided_at.is_(None), LedgerTransaction.routine_payment_id.is_not(None), LedgerTransaction.billing_installment_id.is_not(None))))
    debts = await debt_service.list_debts(user_id, db)
    routines = await list_plans(user_id, billing.local_today().strftime('%Y-%m'), db)
    from app.services.savings_service import list_savings
    savings = await list_savings(user_id, db)
    result = {'Banks': [{'Id': str(row['Id']), 'Label': row['PlatformName'] + ' · ' + row['AccountNumberMasked']} for row in banks],
            'Bills': [{'Id': str(bill.id), 'Label': bill.description + (' · ' + label if label else ''),
                       'PaidInstallments': [{'Id': str(p.id), 'Sequence': p.sequence, 'Amount': int(p.amount), 'Date': local_date(p.paid_at).isoformat()} for p in installments if p.transaction_id == bill.id and p.paid_at and p.id not in recorded],
                       'UnpaidInstallments': [{'Id': str(p.id), 'Sequence': p.sequence, 'Amount': int(p.amount), 'Date': p.due_date.isoformat()} for p in installments if p.transaction_id == bill.id and not p.paid_at][:1]} for bill, label in bills],
            'Debts': [{'Id': str(item['Id']), 'Kind': item['Kind'], 'Label': item['PersonName'], 'RemainingAmount': item['RemainingAmount']} for item in debts if not item['IsSettled']],
            'Routines': [{'Id': item['Id'], 'Kind': item['Kind'], 'Label': (item['Recipient'] + ' · ' if item['Recipient'] else '') + item['Name'],
                'Amount': item['Amount'], 'NextSequence': item['NextSequence'], 'DestinationBankId': item['DestinationBankId'], 'BillingTransactionId': item['BillingTransactionId'], 'DebtId': item['DebtId'], 'SavingId': item['SavingId']} for item in routines if item['Status'] == 'ACTIVE'],
            'Savings': [{'Id': str(item['Id']), 'Label': item['Name'], 'BankAccountId': str(item['BankAccountId']) if item['BankAccountId'] else None, 'Balance': int(item['Balance'])} for item in savings if item['Kind'] == 'CASH']}
    await db.commit()
    return result


async def active_payments(plan_id, db):
    return list(await db.scalars(select(RoutinePayment).where(RoutinePayment.plan_id == plan_id, RoutinePayment.voided_at.is_(None)).order_by(RoutinePayment.sequence)))


async def plan_response(plan, month, db, records=None):
    if records is None:
        records = (await db.execute(select(RoutinePayment, LedgerTransaction).join(LedgerTransaction, LedgerTransaction.routine_payment_id == RoutinePayment.id).where(RoutinePayment.plan_id == plan.id).order_by(RoutinePayment.sequence))).all()
    records = [pair for pair in records if pair[0].plan_id == plan.id]
    payments = [payment for payment, ledger in records if payment.voided_at is None]
    completed = plan.initial_paid + len(payments)
    finished = bool(plan.total_cycles and completed >= plan.total_cycles)
    next_date = None if finished else add_months(plan.first_due_date, len(payments) * plan.interval_months)
    selected = date.fromisoformat(month + '-01')
    offset = (selected.year - plan.first_due_date.year) * 12 + selected.month - plan.first_due_date.month
    scheduled = offset >= 0 and offset % plan.interval_months == 0
    cycle = plan.initial_paid + offset // plan.interval_months + 1 if scheduled else None
    if cycle is not None and plan.total_cycles and cycle > plan.total_cycles:
        cycle = None
    planned = plan.amount if cycle and plan.status == 'ACTIVE' else 0
    history = []
    for payment, ledger in records:
        if payment.voided_at is None:
            history.append({'Id': str(payment.id), 'Sequence': payment.sequence, 'DueDate': payment.due_date.isoformat(), 'Transaction': transaction_response(ledger)})
    paid = sum(row['Transaction']['Amount'] for row in history if row['DueDate'].startswith(month))
    return {'Id': str(plan.id), 'Version': plan.version, 'Kind': plan.kind, 'Recipient': plan.recipient, 'Name': plan.name,
            'Amount': plan.amount, 'Status': 'FINISHED' if finished else plan.status, 'StoredStatus': plan.status,
            'FirstDueDate': plan.first_due_date.isoformat(), 'IntervalMonths': plan.interval_months, 'TotalCycles': plan.total_cycles,
            'InitialPaid': plan.initial_paid, 'DestinationBankId': str(plan.destination_bank_id) if plan.destination_bank_id else None,
            'BillingTransactionId': str(plan.billing_transaction_id) if plan.billing_transaction_id else None,
            'DebtId': str(plan.debt_id) if plan.debt_id else None, 'SavingId': str(plan.saving_id) if plan.saving_id else None, 'Notes': plan.notes,
            'CompletedCycles': completed, 'NextSequence': None if finished else completed + 1,
            'NextDueDate': next_date.isoformat() if next_date else None, 'PlannedAmount': planned, 'PaidAmount': paid,
            'PendingAmount': 0 if any(p.sequence == cycle for p in payments) else planned,
            'CanDelete': not records, 'Payments': history}


async def list_plans(user_id: UUID, month: str, db: AsyncSession) -> list[dict[str, Any]]:
    rows = list(await db.scalars(select(RoutinePlan).where(RoutinePlan.user_id == user_id).order_by(RoutinePlan.recipient, RoutinePlan.name, RoutinePlan.id).with_for_update(read=True)))
    records = (await db.execute(select(RoutinePayment, LedgerTransaction).join(LedgerTransaction, LedgerTransaction.routine_payment_id == RoutinePayment.id).join(RoutinePlan, RoutinePayment.plan_id == RoutinePlan.id).where(RoutinePlan.user_id == user_id).order_by(RoutinePayment.sequence))).all()
    grouped = {}
    for pair in records:
        grouped.setdefault(pair[0].plan_id, []).append(pair)
    return [await plan_response(row, month, db, grouped.get(row.id, [])) for row in rows]


async def save_plan(payload, user_id, month, db, item_id=None):
    from app.services.payment_sync_service import lock_owner
    await lock_owner(user_id, db)
    plan = await owned(RoutinePlan, item_id, user_id, db, True) if item_id else RoutinePlan(id=uuid4(), user_id=user_id, version=1)
    if item_id:
        if payload.version != plan.version:
            raise HTTPException(409, 'Data berubah; muat ulang')
        payments = await active_payments(plan.id, db)
        if payments and any(getattr(plan, key) != getattr(payload, key) for key in ('kind','first_due_date','interval_months','initial_paid','billing_transaction_id','debt_id')):
            invalid('Jenis, jadwal, progres awal dan hubungan Tagihan terkunci setelah pembayaran')
        if payload.total_cycles and payload.total_cycles < payload.initial_paid + len(payments):
            invalid('Jumlah cicilan lebih kecil dari progres pembayaran')
        plan.version += 1
    elif await db.scalar(select(func.count()).select_from(RoutinePlan).where(RoutinePlan.user_id == user_id)) >= 500:
        invalid('Maksimal 500 rencana rutin')
    if payload.destination_bank_id:
        await bank_label(payload.destination_bank_id, user_id, db)
    if payload.saving_id:
        from app.services.savings_sync_service import validate_target
        await validate_target(payload.saving_id, payload.destination_bank_id, user_id, db)
    if payload.billing_transaction_id:
        bill = await db.scalar(select(BillingTransaction).join(BillingAccount, BillingTransaction.account_id == BillingAccount.id).where(BillingTransaction.id == payload.billing_transaction_id, BillingAccount.user_id == user_id))
        if bill is None:
            raise HTTPException(404, 'Bill not found')
    if payload.debt_id:
        debt = await owned(Debt, payload.debt_id, user_id, db)
        if debt.kind != 'DEBT':
            invalid('Setoran rutin hanya dapat terhubung ke Hutang')
    if payload.status == 'ACTIVE':
        for field in ('billing_transaction_id', 'debt_id'):
            target = getattr(payload, field)
            if target and await db.scalar(select(RoutinePlan.id).where(RoutinePlan.user_id == user_id, RoutinePlan.status == 'ACTIVE', getattr(RoutinePlan, field) == target, RoutinePlan.id != plan.id)):
                invalid('Sudah ada rencana aktif yang terhubung ke pembayaran ini')
    for key, value in payload.model_dump(exclude={'version'}).items():
        setattr(plan, key, value)
    db.add(plan)
    await db.flush()
    result = await plan_response(plan, month, db)
    await db.commit()
    return result


async def pay(plan_id, payload, user_id, month, db, commit=True):
    from app.services.payment_sync_service import lock_owner, billing_ledger, debt_ledger
    await lock_owner(user_id, db)
    plan = await owned(RoutinePlan, plan_id, user_id, db, True)
    repeat = await db.scalar(select(RoutinePayment).where(RoutinePayment.plan_id == plan_id, RoutinePayment.request_id == payload.request_id))
    if repeat:
        ledger = await db.scalar(select(LedgerTransaction).where(LedgerTransaction.routine_payment_id == repeat.id))
        if repeat.voided_at or (repeat.sequence, ledger.amount, ledger.source_bank_id, ledger.billing_installment_id, ledger.notes) != (payload.sequence, payload.amount, payload.source_bank_id, payload.billing_installment_id, payload.notes) or (not plan.billing_transaction_id and ledger.transaction_date != payload.payment_date):
            raise HTTPException(409, 'Permintaan pembayaran telah digunakan')
        return await plan_response(plan, month, db)
    paid = await active_payments(plan_id, db)
    sequence = plan.initial_paid + len(paid) + 1
    if plan.status != 'ACTIVE' or (plan.total_cycles and sequence > plan.total_cycles) or payload.sequence != sequence:
        raise HTTPException(409, 'Rencana tidak aktif atau cicilan sudah berubah')
    source = await bank_label(payload.source_bank_id, user_id, db)
    destination = await bank_label(plan.destination_bank_id, user_id, db) if plan.kind == 'TRANSFER' else ''
    if plan.kind == 'TRANSFER' and (not payload.source_bank_id or not plan.destination_bank_id or payload.source_bank_id == plan.destination_bank_id):
        invalid('Pilih dua rekening berbeda milik sendiri')
    if plan.billing_transaction_id:
        from app.services import billing_transaction_service as billing
        item = await billing.owned_transaction(plan.billing_transaction_id, user_id, db, lock=True)
        bill = await db.scalar(select(BillingInstallment).where(BillingInstallment.id == payload.billing_installment_id, BillingInstallment.transaction_id == item.id))
        if bill is None or int(bill.amount) != payload.amount or bill.amount != int(bill.amount):
            invalid('Pilih Tagihan dengan nominal pembayaran yang sama')
        existing = await db.scalar(select(LedgerTransaction).where(LedgerTransaction.billing_installment_id == bill.id, LedgerTransaction.voided_at.is_(None)))
        if existing and existing.routine_payment_id:
            raise HTTPException(409, 'Pembayaran sudah terhubung ke rencana rutin')
        if bill.paid_at is None:
            await billing.mark_paid(item.id, bill.id, user_id, db, commit=False, sync=False)
        ledger = await billing_ledger(item, bill, user_id, db, payload.source_bank_id, payload.notes, plan, payload.request_id)
        await db.flush()
        result = await plan_response(plan, month, db)
        if commit:
            await db.commit()
        return result
    elif payload.billing_installment_id:
        invalid('Rencana tidak terhubung ke Tagihan')
    if plan.debt_id:
        from app.services import debt_service
        from app.schemas.debt_schema import PaymentCreate
        await debt_service.add_payment(plan.debt_id, PaymentCreate.model_validate({
            'RequestId': payload.request_id, 'Amount': payload.amount, 'PaymentDate': payload.payment_date,
            'BankAccountId': payload.source_bank_id, 'Notes': payload.notes}), user_id, db, commit=False, sync=False)
        item = await owned(Debt, plan.debt_id, user_id, db)
        payment = await db.scalar(select(DebtPayment).where(DebtPayment.debt_id == item.id, DebtPayment.request_id == payload.request_id))
        await debt_ledger(item, payment, user_id, db, payload.source_bank_id, plan, payload.request_id)
        result = await plan_response(plan, month, db)
        if commit:
            await db.commit()
        return result
    payment = RoutinePayment(id=uuid4(), plan_id=plan.id, request_id=payload.request_id, sequence=sequence,
                             due_date=add_months(plan.first_due_date, len(paid) * plan.interval_months))
    db.add(payment)
    await db.flush()
    ledger = LedgerTransaction(user_id=user_id, kind='transfer' if plan.kind == 'TRANSFER' else 'expense',
        category='savings' if plan.kind == 'TRANSFER' else 'bills' if plan.kind == 'SUBSCRIPTION' else 'family',
        description=(plan.recipient + ' · ' if plan.recipient else '') + plan.name,
        amount=payload.amount, transaction_date=payload.payment_date, source_bank_id=payload.source_bank_id,
        destination_bank_id=plan.destination_bank_id if plan.kind == 'TRANSFER' else None, source_label=source, destination_label=destination,
        notes=payload.notes, routine_payment_id=payment.id, billing_installment_id=payload.billing_installment_id)
    db.add(ledger)
    if plan.saving_id:
        from app.services.savings_sync_service import apply_movement
        await apply_movement(ledger, plan.saving_id, 'ADD', payload.request_id, user_id, db)
    plan.version += 1
    await db.flush()
    result = await plan_response(plan, month, db)
    if commit:
        await db.commit()
    return result


async def undo(plan_id, payment_id, user_id, month, db):
    from app.services.payment_sync_service import lock_owner
    await lock_owner(user_id, db)
    plan = await owned(RoutinePlan, plan_id, user_id, db, True)
    payments = await active_payments(plan_id, db)
    if not payments or payments[-1].id != payment_id:
        raise HTTPException(409, 'Hanya pembayaran terakhir yang dapat dibatalkan')
    payment = payments[-1]
    ledger = await db.scalar(select(LedgerTransaction).where(LedgerTransaction.routine_payment_id == payment.id))
    if ledger.billing_installment_id or ledger.debt_payment_id:
        raise HTTPException(409, 'Pembayaran tertaut tidak dapat dibatalkan lewat Pengeluaran Rutin')
    if ledger.saving_movement_id:
        from app.services.savings_sync_service import reverse_movement
        await reverse_movement(ledger, user_id, db)
    payment.voided_at = ledger.voided_at = datetime.now(timezone.utc)
    plan.version += 1
    await db.flush()
    result = await plan_response(plan, month, db)
    await db.commit()
    return result


async def linked_transaction(payload, user_id, db):
    from app.services import billing_transaction_service as billing, debt_service
    from app.services.payment_sync_service import billing_ledger, debt_ledger
    from app.schemas.debt_schema import PaymentCreate
    from app.schemas.routine_schema import PaymentInput
    if payload.debt_id:
        item = await owned(Debt, payload.debt_id, user_id, db)
        expected = 'income' if item.kind == 'RECEIVABLE' else 'expense'
        if payload.kind != expected:
            invalid('Jenis transaksi tidak sesuai Hutang/Piutang yang dipilih')
        bank = payload.destination_bank_id if expected == 'income' else payload.source_bank_id
        await debt_service.add_payment(item.id, PaymentCreate.model_validate({
            'RequestId': payload.request_id, 'Amount': payload.amount, 'PaymentDate': payload.transaction_date,
            'Notes': payload.notes, 'BankAccountId': bank}), user_id, db, commit=False)
        payment = await db.scalar(select(DebtPayment).where(DebtPayment.debt_id == item.id, DebtPayment.request_id == payload.request_id))
        return await debt_ledger(item, payment, user_id, db, bank)
    if payload.billing_installment_id:
        bill = await db.get(BillingInstallment, payload.billing_installment_id)
        if bill is None:
            raise HTTPException(404, 'Bill not found')
        item = await billing.owned_transaction(bill.transaction_id, user_id, db, lock=True)
        if payload.kind != 'expense' or payload.amount != bill.amount:
            invalid('Pembayaran Tagihan harus Pengeluaran dengan nominal tepat')
        await billing.mark_paid(item.id, bill.id, user_id, db, commit=False, sync=False)
        return await billing_ledger(item, bill, user_id, db, payload.source_bank_id, payload.notes)
    plan = await owned(RoutinePlan, payload.routine_plan_id, user_id, db, True)
    expected = 'transfer' if plan.kind == 'TRANSFER' else 'expense'
    if payload.kind != expected or (expected == 'transfer' and payload.destination_bank_id != plan.destination_bank_id):
        invalid('Jenis atau rekening tujuan tidak sesuai rencana rutin')
    installment_id = None
    if plan.billing_transaction_id:
        item = await billing.owned_transaction(plan.billing_transaction_id, user_id, db, lock=True)
        await billing.generate_subscription(item, db)
        installment_id = await db.scalar(select(BillingInstallment.id).where(BillingInstallment.transaction_id == item.id,
            BillingInstallment.paid_at.is_(None)).order_by(BillingInstallment.sequence).limit(1))
        if not installment_id:
            raise HTTPException(409, 'Tidak ada Tagihan yang belum dibayar')
    await pay(plan.id, PaymentInput.model_validate({
        'RequestId': payload.request_id, 'Sequence': payload.routine_sequence, 'Amount': payload.amount,
        'PaymentDate': payload.transaction_date, 'SourceBankId': payload.source_bank_id,
        'BillingInstallmentId': installment_id, 'Notes': payload.notes}), user_id, payload.transaction_date.strftime('%Y-%m'), db, commit=False)
    payment = await db.scalar(select(RoutinePayment).where(RoutinePayment.plan_id == plan.id, RoutinePayment.request_id == payload.request_id))
    return await db.scalar(select(LedgerTransaction).where(LedgerTransaction.routine_payment_id == payment.id))


async def remove_plan(plan_id, user_id, db):
    plan = await owned(RoutinePlan, plan_id, user_id, db, True)
    if await db.scalar(select(RoutinePayment.id).where(RoutinePayment.plan_id == plan_id).limit(1)):
        raise HTTPException(409, 'Rencana bersejarah dapat dihentikan, bukan dihapus')
    await db.delete(plan)
    await db.commit()
