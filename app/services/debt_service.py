from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select

from app.models.debt_model import Debt, DebtPayment
from app.models.bank_account_model import BankAccount
from app.models.billing_model import WalletProvider
from app.helpers.bank_encryption import masked
from app.services.billing_transaction_service import local_today, month_date


def invalid(field, message):
    raise HTTPException(422, [{"loc": ["body", field], "msg": message, "type": "value_error"}])


def validate(payload):
    if payload.transaction_date > local_today():
        invalid("TransactionDate", "Tanggal transaksi tidak boleh melewati hari ini")
    if payload.due_date and payload.due_date < payload.transaction_date:
        invalid("DueDate", "Jatuh tempo tidak boleh sebelum tanggal transaksi")
    if payload.interest_type == "NONE" and payload.interest_rate != 0:
        invalid("InterestRate", "Tanpa bunga harus memiliki bunga 0")
    if payload.interest_type == "MONTHLY" and payload.interest_rate <= 0:
        invalid("InterestRate", "Bunga bulanan harus lebih dari 0")
    if payload.kind != 'RECEIVABLE' and payload.source_bank_account_id:
        invalid('SourceBankAccountId', 'Asal dana hanya berlaku untuk Piutang')
    if payload.installment_count and not payload.due_date:
        invalid('DueDate', 'Tanggal pengembalian pertama wajib untuk cicilan')
    if payload.installment_count and payload.due_date and payload.due_date.year > 9994:
        invalid('DueDate', 'Tanggal awal cicilan maksimal tahun 9994')
    if not payload.installment_count and payload.installment_amounts:
        invalid('InstallmentAmounts', 'Tanpa cicilan tidak boleh memiliki rincian cicilan')
    if payload.installment_count:
        if payload.principal < payload.installment_count:
            invalid('Principal', 'Pokok minimal satu rupiah per cicilan')
        if payload.installment_amounts is not None:
            validate_amounts(payload.installment_amounts, payload.installment_count, payload.principal)


def validate_amounts(amounts, count, principal):
    if len(amounts) != count or any(x <= 0 or x > 1000000000000 for x in amounts) or sum(amounts) != principal:
        invalid('InstallmentAmounts', 'Jumlah cicilan harus sesuai tenor, positif, dan total nominal pokok harus sama dengan pokok transaksi')


def default_amounts(principal, count):
    if not count:
        return []
    amount, remainder = divmod(principal, count)
    return [amount] * (count - 1) + [amount + remainder]


async def set_source(item, source_id, user_id, db):
    if source_id is None:
        item.source_bank_account_id = item.source_bank_name = item.source_account_number_masked = None
        return
    account = await db.scalar(select(BankAccount).where(BankAccount.id == source_id, BankAccount.user_id == user_id).with_for_update())
    if account is None:
        invalid('SourceBankAccountId', 'Rekening asal dana tidak tersedia atau bukan milik Anda')
    provider = await db.get(WalletProvider, account.platform_id)
    item.source_bank_account_id = account.id
    item.source_bank_name = provider.name
    item.source_account_number_masked = masked(account.account_number_encrypted, account.id, user_id, 'account')


def ledger(item, payments, through=None):
    """Replay monthly anniversaries and dated payments; GET never writes rows.

    Each month's interest is rounded to whole rupiah, based only on remaining
    principal (no compounding). Anniversary interest is charged before payments
    dated that day. Original day is restored after February/short months.
    """
    through = through or local_today()
    principal, interest, accrued, paid = int(item.principal), 0, 0, 0
    offset, charges, allocations = 1, [], []
    rate = Decimal(str(item.interest_rate))

    def accrue(until):
        nonlocal offset, interest, accrued
        if item.interest_type != "MONTHLY":
            return
        while principal > 0:
            charge_date = month_date(item.transaction_date, offset, item.transaction_date.day)
            if charge_date > until:
                break
            amount = int((Decimal(principal) * rate / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
            interest += amount
            accrued += amount
            charges.append({"Date": charge_date, "PrincipalBase": principal, "Amount": amount})
            offset += 1

    for payment in sorted(payments, key=lambda p: p.sequence):
        if payment.payment_date > through:
            break
        accrue(payment.payment_date)
        amount = int(payment.amount)
        interest_portion = min(amount, interest)
        principal_portion = amount - interest_portion
        if principal_portion > principal:
            raise HTTPException(409, "Payment history exceeds balance")
        interest -= interest_portion
        principal -= principal_portion
        paid += amount
        allocations.append({"Id": payment.id, "Sequence": payment.sequence, "Amount": amount,
                            "PaymentDate": payment.payment_date, "Notes": payment.notes,
                            "InterestPortion": interest_portion, "PrincipalPortion": principal_portion})
    accrue(through)
    remaining = principal + interest
    # Retain the ledger permanently; only list visibility expires. Use the
    # recorded final payment date, including backdated settlements.
    history_visible = remaining != 0 or not allocations or through < month_date(
        allocations[-1]['PaymentDate'], 3, allocations[-1]['PaymentDate'].day)
    schedule, applied = [], int(item.principal) - principal
    for index, amount in enumerate(item.installment_amounts or []):
        allocated = min(applied, amount)
        applied -= allocated
        schedule.append({'Sequence': index + 1, 'DueDate': month_date(item.due_date, index, item.due_date.day),
                         'PrincipalAmount': amount, 'PaidPrincipal': allocated, 'RemainingPrincipal': amount - allocated, 'IsPaid': allocated == amount})
    overdue = any(bill['RemainingPrincipal'] and bill['DueDate'] < through for bill in schedule) if schedule else bool(remaining and item.due_date and item.due_date < through)
    if schedule and interest and schedule[-1]['DueDate'] < through:
        overdue = True
    return {
        "Id": item.id, "Kind": item.kind, "PersonName": item.person_name,
        "Principal": int(item.principal), "TransactionDate": item.transaction_date,
        "DueDate": item.due_date, "InterestType": item.interest_type,
        "SourceBankAccountId": item.source_bank_account_id, "SourceBankName": item.source_bank_name,
        "SourceAccountNumberMasked": item.source_account_number_masked,
        "InstallmentCount": item.installment_count or 0, "Installments": schedule,
        "InterestRate": float(rate), "Notes": item.notes,
        "InterestAccrued": accrued, "TotalAmount": int(item.principal) + accrued,
        "PaidAmount": paid, "RemainingPrincipal": principal,
        "RemainingInterest": interest, "RemainingAmount": remaining,
        "IsSettled": remaining == 0,
        "IsHistoryVisible": history_visible,
        "IsOverdue": bool(overdue),
        "CanDelete": not payments,
        "NextInterestDate": month_date(item.transaction_date, offset, item.transaction_date.day)
            if item.interest_type == "MONTHLY" and principal > 0 else None,
        "Payments": allocations, "InterestCharges": charges,
    }


async def owned(debt_id, user_id, db, lock=False):
    query = select(Debt).where(Debt.id == debt_id, Debt.user_id == user_id)
    if lock:
        query = query.with_for_update()
    item = await db.scalar(query)
    if item is None:
        raise HTTPException(404, "Debt not found")
    return item


async def payments_for(item, db):
    return (await db.scalars(select(DebtPayment).where(DebtPayment.debt_id == item.id)
                            .order_by(DebtPayment.sequence))).all()


async def create(payload, user_id, db):
    validate(payload)
    values = payload.model_dump(exclude={'source_bank_account_id', 'installment_amounts'})
    item = Debt(user_id=user_id, **values, installment_amounts=payload.installment_amounts or default_amounts(payload.principal, payload.installment_count))
    await set_source(item, payload.source_bank_account_id, user_id, db)
    db.add(item)
    await db.commit()
    return ledger(item, [])


async def list_debts(user_id, db):
    # One joined query keeps each read consistent and avoids per-row DB requests.
    rows = (await db.execute(select(Debt, DebtPayment).outerjoin(DebtPayment, DebtPayment.debt_id == Debt.id)
                            .where(Debt.user_id == user_id).order_by(Debt.person_name, Debt.id, DebtPayment.sequence))).all()
    grouped = {}
    for item, payment in rows:
        grouped.setdefault(item.id, (item, []))
        if payment:
            grouped[item.id][1].append(payment)
    today = local_today()
    summaries = [ledger(item, payments, today) for item, payments in grouped.values()]
    return [item for item in summaries if item['IsHistoryVisible']]


async def detail(debt_id, user_id, db):
    item = await owned(debt_id, user_id, db)
    return ledger(item, await payments_for(item, db))


async def update(debt_id, payload, user_id, db):
    validate(payload)
    item = await owned(debt_id, user_id, db, lock=True)
    payments = await payments_for(item, db)
    # Payment history fixes the original financial terms. Names/notes/due date can change.
    if payments and any(getattr(item, field) != getattr(payload, field)
                        for field in ("kind", "principal", "transaction_date", "interest_type", "interest_rate")):
        raise HTTPException(409, "Financial terms cannot change after a payment")
    count = payload.installment_count if 'installment_count' in payload.model_fields_set else item.installment_count
    if payments and (count != item.installment_count or (count and payload.due_date != item.due_date)):
        raise HTTPException(409, 'Jadwal cicilan tidak dapat berubah setelah pembayaran')
    if count and not payload.due_date:
        invalid('DueDate', 'Tanggal pengembalian pertama wajib untuk cicilan')
    if count and payload.due_date.year > 9994:
        invalid('DueDate', 'Tanggal awal cicilan maksimal tahun 9994')
    amounts = payload.installment_amounts
    if amounts is None:
        amounts = item.installment_amounts if count == item.installment_count and payload.principal == int(item.principal) else default_amounts(payload.principal, count)
    if count:
        validate_amounts(amounts, count, payload.principal)
    elif amounts:
        invalid('InstallmentAmounts', 'Tanpa cicilan tidak boleh memiliki rincian cicilan')
    if payments:
        current = ledger(item, payments)
        for bill in current['Installments']:
            if bill['PaidPrincipal'] and amounts[bill['Sequence'] - 1] != bill['PrincipalAmount']:
                raise HTTPException(409, 'Nominal cicilan yang sudah dibayar tidak dapat diubah')
    if payload.kind != 'RECEIVABLE':
        await set_source(item, None, user_id, db)
    elif 'source_bank_account_id' in payload.model_fields_set:
        if payload.source_bank_account_id != item.source_bank_account_id:
            await set_source(item, payload.source_bank_account_id, user_id, db)
        elif payload.source_bank_account_id is None:
            await set_source(item, None, user_id, db)
    item.installment_count, item.installment_amounts = count, amounts
    for key, value in payload.model_dump(exclude={'source_bank_account_id', 'installment_count', 'installment_amounts'}).items():
        setattr(item, key, value)
    await db.commit()
    return ledger(item, payments)


async def update_installments(debt_id, payload, user_id, db):
    item = await owned(debt_id, user_id, db, lock=True)
    payments = await payments_for(item, db)
    if not item.installment_count:
        raise HTTPException(409, 'Transaksi ini tidak memiliki cicilan')
    validate_amounts(payload.amounts, item.installment_count, int(item.principal))
    current = ledger(item, payments)
    for bill in current['Installments']:
        if bill['PaidPrincipal'] and payload.amounts[bill['Sequence'] - 1] != bill['PrincipalAmount']:
            raise HTTPException(409, 'Nominal cicilan yang sudah dibayar tidak dapat diubah')
    item.installment_amounts = payload.amounts
    await db.commit()
    return ledger(item, payments)


async def delete(debt_id, user_id, db):
    item = await owned(debt_id, user_id, db, lock=True)
    if await payments_for(item, db):
        raise HTTPException(409, "Payment history must be retained")
    await db.delete(item)
    await db.commit()


async def add_payment(debt_id, payload, user_id, db, commit=True, sync=True):
    from app.services.payment_sync_service import lock_owner, debt_ledger
    from app.services.routine_service import bank_label
    await lock_owner(user_id, db)
    await bank_label(payload.bank_account_id, user_id, db)
    item = await owned(debt_id, user_id, db, lock=True)
    payments = await payments_for(item, db)
    previous = next((p for p in payments if p.request_id == payload.request_id), None)
    if previous:
        if (int(previous.amount), previous.payment_date, previous.notes) != (payload.amount, payload.payment_date, payload.notes):
            raise HTTPException(409, "RequestId already used for a different payment")
        if sync:
            await debt_ledger(item, previous, user_id, db, payload.bank_account_id)
            if commit:
                await db.commit()
        return ledger(item, payments)
    minimum_date = payments[-1].payment_date if payments else item.transaction_date
    if payload.payment_date < minimum_date or payload.payment_date > local_today():
        invalid("PaymentDate", "Tanggal pembayaran harus berurutan, sejak tanggal transaksi sampai hari ini")
    at_payment = ledger(item, payments, payload.payment_date)
    if payload.amount > at_payment["RemainingAmount"]:
        invalid("Amount", "Nominal melebihi sisa pada tanggal pembayaran")
    payment = DebtPayment(debt_id=item.id, sequence=len(payments) + 1, **payload.model_dump(exclude={'bank_account_id'}))
    db.add(payment)
    await db.flush()
    if sync:
        await debt_ledger(item, payment, user_id, db, payload.bank_account_id)
    if commit:
        await db.commit()
    return ledger(item, [*payments, payment])
