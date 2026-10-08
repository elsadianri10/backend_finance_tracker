from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select, delete as sql_delete
from app.models.savings_model import Saving, SavingMovement
from app.models.bank_account_model import BankAccount
from app.models.billing_model import WalletProvider
from app.helpers.bank_encryption import masked
from app.services.debt_service import invalid
from app.services.billing_transaction_service import local_today


def metal_type(payload, existing=None):
    if payload.kind != 'GOLD':
        return None
    if 'metal_type' in payload.model_fields_set:
        if payload.metal_type is None:
            invalid('MetalType', 'Pilih Emas atau Perak')
        return payload.metal_type
    return (existing.metal_type if existing and existing.kind == 'GOLD' else None) or 'GOLD'


def validate(payload, existing=None):
    metal_type(payload, existing)
    if payload.kind != 'GOLD' and payload.metal_type is not None:
        invalid('MetalType', 'Jenis logam hanya berlaku untuk Logam Mulia')
    if payload.start_date > local_today():
        invalid('StartDate', 'Tanggal mulai tidak boleh melewati hari ini')
    if payload.kind == 'GOLD':
        if payload.weight_per_piece is None or payload.pieces is None:
            invalid('WeightPerPiece', 'Berat dan jumlah keping wajib diisi')
        if payload.weight_per_piece * payload.pieces > 1000000:
            invalid('WeightPerPiece', 'Total logam maksimal 1.000.000 gram')
        if payload.opening_amount is not None or payload.bank_account_id is not None:
            invalid('OpeningAmount', 'Logam Mulia menggunakan berat, bukan nominal atau rekening')
    else:
        if payload.opening_amount is None:
            invalid('OpeningAmount', 'Nominal awal wajib diisi')
        if any(getattr(payload, field) is not None for field in ('weight_per_piece', 'pieces', 'purchase_cost', 'price_per_gram')):
            invalid('WeightPerPiece', 'Field logam hanya berlaku untuk Logam Mulia')
    if payload.kind == 'DEPOSIT':
        if not payload.maturity_date or payload.maturity_date < payload.start_date:
            invalid('MaturityDate', 'Jatuh tempo wajib diisi dan tidak sebelum tanggal mulai')
        if not payload.bank_account_id and not (existing and existing.bank_name and 'bank_account_id' not in payload.model_fields_set):
            invalid('BankAccountId', 'Pilih rekening bank untuk deposito')
    elif payload.maturity_date is not None or payload.interest_rate is not None:
        invalid('MaturityDate', 'Jatuh tempo dan bunga hanya untuk deposito')


async def owned(saving_id, user_id, db, lock=False):
    query = select(Saving).where(Saving.id == saving_id, Saving.user_id == user_id)
    item = await db.scalar(query.with_for_update() if lock else query)
    if not item:
        raise HTTPException(404, 'Saving not found')
    return item


async def movements_for(item, db):
    return list((await db.scalars(select(SavingMovement).where(SavingMovement.saving_id == item.id).order_by(SavingMovement.sequence))).all())


def response(item, movements):
    balance = item.opening_amount + sum((m.amount if m.direction == 'ADD' else -m.amount for m in movements), Decimal(0))
    estimated = int((balance * item.price_per_gram).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if item.kind == 'GOLD' and item.price_per_gram else None
    result = {''.join(p.capitalize() for p in field.split('_')): getattr(item, field) for field in
              ('id', 'kind', 'metal_type', 'name', 'opening_amount', 'start_date', 'bank_account_id', 'bank_name', 'bank_account_masked',
               'weight_per_piece', 'pieces', 'purchase_cost', 'price_per_gram', 'price_date', 'maturity_date', 'interest_rate', 'notes')}
    result.update(Balance=balance, EstimatedValue=estimated, Movements=[{'Id': m.id, 'Sequence': m.sequence,
                  'Direction': m.direction, 'Amount': m.amount, 'MovementDate': m.movement_date, 'Notes': m.notes} for m in movements])
    return result


async def set_values(item, payload, user_id, db):
    # Only a new/changed price refreshes its date; metadata edits retain it.
    if payload.kind != 'GOLD' or payload.price_per_gram is None:
        item.price_date = None
    elif payload.price_per_gram != item.price_per_gram:
        item.price_date = local_today()
    item.metal_type = metal_type(payload, item)
    if payload.kind == 'GOLD':
        item.bank_account_id = item.bank_name = item.bank_account_masked = None
    if 'bank_account_id' in payload.model_fields_set or not item.id:
        if payload.bank_account_id:
            if payload.bank_account_id != item.bank_account_id:
                bank = await db.scalar(select(BankAccount).where(BankAccount.id == payload.bank_account_id, BankAccount.user_id == user_id).with_for_update())
                if not bank:
                    invalid('BankAccountId', 'Rekening tidak tersedia atau bukan milik Anda')
                provider = await db.get(WalletProvider, bank.platform_id)
                item.bank_account_id, item.bank_name = bank.id, provider.name
                item.bank_account_masked = masked(bank.account_number_encrypted, bank.id, user_id, 'account')
        else:
            item.bank_account_id = item.bank_name = item.bank_account_masked = None
    for key, value in payload.model_dump(exclude={'bank_account_id', 'opening_amount', 'metal_type'}).items():
        setattr(item, key, value)
    item.opening_amount = payload.weight_per_piece * payload.pieces if payload.kind == 'GOLD' else Decimal(payload.opening_amount)


async def create(payload, user_id, db):
    validate(payload)
    item = Saving(user_id=user_id)
    await set_values(item, payload, user_id, db)
    db.add(item)
    await db.commit()
    return response(item, [])


async def list_savings(user_id, db):
    rows = (await db.execute(select(Saving, SavingMovement).outerjoin(SavingMovement, SavingMovement.saving_id == Saving.id)
             .where(Saving.user_id == user_id).order_by(Saving.name, Saving.id, SavingMovement.sequence))).all()
    grouped = {}
    for item, movement in rows:
        grouped.setdefault(item.id, (item, []))
        if movement:
            grouped[item.id][1].append(movement)
    return [response(item, movements) for item, movements in grouped.values()]


async def detail(saving_id, user_id, db):
    item = await owned(saving_id, user_id, db)
    return response(item, await movements_for(item, db))


async def update(saving_id, payload, user_id, db):
    item = await owned(saving_id, user_id, db, True)
    validate(payload, item)
    movements = await movements_for(item, db)
    opening = payload.weight_per_piece * payload.pieces if payload.kind == 'GOLD' else Decimal(payload.opening_amount)
    if movements and (payload.kind != item.kind or metal_type(payload, item) != item.metal_type or opening != item.opening_amount or payload.start_date != item.start_date
                      or payload.weight_per_piece != item.weight_per_piece or payload.pieces != item.pieces):
        raise HTTPException(409, 'Saldo awal dan jenis terkunci setelah ada riwayat; gunakan tambah/kurangi simpanan')
    await set_values(item, payload, user_id, db)
    await db.commit()
    return response(item, movements)


async def delete(saving_id, user_id, db):
    item = await owned(saving_id, user_id, db, True)
    await db.execute(sql_delete(SavingMovement).where(SavingMovement.saving_id == item.id))
    await db.delete(item)
    await db.commit()


async def add_movement(saving_id, payload, user_id, db):
    item = await owned(saving_id, user_id, db, True)
    movements = await movements_for(item, db)
    previous = next((m for m in movements if m.request_id == payload.request_id), None)
    if previous:
        if (previous.direction, previous.amount, previous.movement_date, previous.notes) != (payload.direction, payload.amount, payload.movement_date, payload.notes):
            raise HTTPException(409, 'RequestId already used')
        return response(item, movements)
    if item.kind != 'GOLD' and payload.amount != payload.amount.to_integral_value():
        invalid('Amount', 'Nominal rupiah harus bilangan bulat')
    minimum = movements[-1].movement_date if movements else item.start_date
    if not minimum <= payload.movement_date <= local_today():
        invalid('MovementDate', 'Tanggal harus berurutan, sejak tanggal mulai hingga hari ini')
    if payload.direction == 'REMOVE' and payload.amount > response(item, movements)['Balance']:
        invalid('Amount', 'Jumlah melebihi simpanan yang tersedia')
    if payload.direction == 'ADD' and response(item, movements)['Balance'] + payload.amount > (1000000 if item.kind == 'GOLD' else 1000000000000):
        invalid('Amount', 'Jumlah simpanan melewati batas yang didukung')
    movement = SavingMovement(saving_id=item.id, sequence=len(movements) + 1, **payload.model_dump())
    db.add(movement)
    await db.commit()
    return response(item, [*movements, movement])
