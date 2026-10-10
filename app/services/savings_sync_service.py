from uuid import uuid5
from sqlalchemy import select
from app.models.savings_model import SavingMovement
from app.schemas.savings_schema import MovementCreate
from app.services import savings_service
from app.services.routine_service import invalid


async def record_origin(saving, movement, payload, user_id, db, repeat=False):
    from hashlib import sha256
    from fastapi import HTTPException
    from app.models.routine_model import LedgerTransaction
    from app.services.routine_service import bank_label
    fingerprint = sha256(payload.model_dump_json().encode()).hexdigest()
    existing = await db.scalar(select(LedgerTransaction).where(LedgerTransaction.saving_movement_id == movement.id))
    if existing:
        if existing.request_hash != fingerprint or existing.voided_at:
            raise HTTPException(409, 'Permintaan pembayaran telah digunakan')
        return existing
    if repeat:
        raise HTTPException(409, 'Riwayat lama tidak dapat dicatat ulang sebagai Transaksi')
    if saving.kind != 'CASH' or not saving.bank_account_id:
        savings_service.invalid('RecordTransaction', 'Pencatatan Transaksi memerlukan Tabungan Uang dengan rekening bank')
    destination = await bank_label(saving.bank_account_id, user_id, db)
    add = movement.direction == 'ADD'
    if add and (not payload.source_bank_id or payload.source_bank_id == saving.bank_account_id):
        savings_service.invalid('SourceBankId', 'Pilih rekening sumber yang berbeda dari rekening Savings')
    if not add and payload.source_bank_id:
        savings_service.invalid('SourceBankId', 'Tarik Tunai memakai rekening Savings sebagai sumber')
    source = await bank_label(payload.source_bank_id, user_id, db) if add else destination
    row = LedgerTransaction(user_id=user_id, kind='transfer' if add else 'income',
        category='savings' if add else 'cash_withdrawal',
        description=('Alokasi Tabungan · ' if add else 'Tarik Tunai · ') + saving.name,
        amount=int(movement.amount), transaction_date=movement.movement_date,
        source_bank_id=payload.source_bank_id if add else saving.bank_account_id,
        destination_bank_id=saving.bank_account_id if add else None,
        source_label=source, destination_label=destination if add else '', notes=movement.notes,
        saving_movement_id=movement.id, request_id=uuid5(movement.request_id, 'savings-origin:' + str(saving.id)),
        request_hash=fingerprint)
    db.add(row)
    await db.flush()
    return row


async def validate_target(saving_id, bank_id, user_id, db):
    saving = await savings_service.owned(saving_id, user_id, db, True)
    if saving.kind != 'CASH':
        invalid('Pilih Savings jenis Tabungan Uang')
    if saving.bank_account_id != bank_id:
        invalid('Rekening harus sesuai dengan rekening Savings yang dipilih')
    return saving


async def apply_movement(ledger, saving_id, direction, request_id, user_id, db):
    bank_id = ledger.source_bank_id if direction == 'REMOVE' else ledger.destination_bank_id
    await validate_target(saving_id, bank_id, user_id, db)
    movement_request = uuid5(request_id, 'saving-movement')
    await savings_service.add_movement(saving_id, MovementCreate.model_validate({
        'RequestId': movement_request, 'Direction': direction, 'Amount': ledger.amount,
        'MovementDate': ledger.transaction_date, 'Notes': ledger.description}), user_id, db, commit=False)
    movement = await db.scalar(select(SavingMovement).where(SavingMovement.saving_id == saving_id, SavingMovement.request_id == movement_request))
    ledger.saving_movement_id = movement.id


async def reverse_movement(ledger, user_id, db):
    movement = await db.get(SavingMovement, ledger.saving_movement_id)
    await savings_service.add_movement(movement.saving_id, MovementCreate.model_validate({
        'RequestId': uuid5(ledger.id, 'saving-reversal'),
        'Direction': 'REMOVE' if movement.direction == 'ADD' else 'ADD', 'Amount': movement.amount,
        'MovementDate': savings_service.local_today(), 'Notes': 'Pembatalan · ' + ledger.description}), user_id, db, commit=False)
