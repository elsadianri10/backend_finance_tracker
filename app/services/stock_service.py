"""Package inventory and explicit replenishment; reminders never mutate stock."""
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.models.stock_model import StockNeed, StockProduct, StockEvent
from app.models.routine_model import LedgerTransaction
from app.services.payment_sync_service import lock_owner
from app.services.routine_service import add_months, bank_label


def today():
    return datetime.now(timezone(timedelta(hours=7))).date()


def fields(row, names):
    return {''.join(part.title() for part in key.split('_')): getattr(row, key) for key in names.split()}


def reason(need, products, day):
    if need.archived or need.paused or need.snoozed_until and need.snoozed_until > day:
        return None
    if need.buy_requested:
        return 'requested'
    available = [p for p in products if not p.archived]
    if any(p.near_empty for p in available) and sum(p.reserve_count for p in available) == 0:
        return 'near_empty'
    if need.mode == 'monthly' and need.next_review and need.next_review <= day:
        return 'due'
    if need.mode == 'low_stock' and available and sum(p.reserve_count for p in available) <= need.reserve_threshold:
        return 'low_stock'
    return None


async def output(needs, db):
    products = list(await db.scalars(select(StockProduct).where(StockProduct.need_id.in_([n.id for n in needs])).order_by(StockProduct.brand, StockProduct.variant, StockProduct.id)))
    result = []
    for need in needs:
        own = [p for p in products if p.need_id == need.id]
        value = fields(need, 'id name category subcategory mode reserve_threshold next_review snoozed_until paused archived buy_requested notes version')
        value['Products'] = [fields(p, 'id brand variant package_unit package_size preference active_count reserve_count near_empty opened_on archived version') for p in own]
        value['BuyReason'] = reason(need, own, today())
        result.append(value)
    return result


async def one(need, db):
    return (await output([need], db))[0]


async def listed(user, db):
    return await output(list(await db.scalars(select(StockNeed).where(StockNeed.user_id == user.id).order_by(StockNeed.name, StockNeed.id))), db)


async def owned(need_id, user, db, lock=True):
    if lock:
        # Same lock ordering as financial services keeps purchase + ledger atomic.
        await lock_owner(user.id, db)
    row = await db.scalar(select(StockNeed).where(StockNeed.id == need_id, StockNeed.user_id == user.id).with_for_update() if lock else select(StockNeed).where(StockNeed.id == need_id, StockNeed.user_id == user.id))
    if row is None:
        raise HTTPException(404, 'Kebutuhan tidak ditemukan')
    return row


def version(row, expected):
    if row.version != expected:
        raise HTTPException(409, 'Data stok sudah berubah. Muat ulang sebelum mencoba lagi.')


async def save_need(need_id, payload, user, db):
    if need_id:
        need = await owned(need_id, user, db)
        version(need, payload.version)
        need.version += 1
    else:
        need = StockNeed(user_id=user.id, version=1)
        db.add(need)
    for key, value in payload.model_dump(exclude={'version'}).items():
        setattr(need, key, value)
    await db.commit()
    return await one(need, db)


async def control(need_id, payload, user, db):
    need = await owned(need_id, user, db)
    version(need, payload.version)
    if payload.action == 'pause':
        need.paused = True
    elif payload.action == 'resume':
        need.paused = False
        need.snoozed_until = None
    elif payload.action == 'skip':
        if need.mode != 'monthly':
            raise HTTPException(422, 'Lewati bulan ini tersedia untuk pengingat bulanan')
        need.snoozed_until = add_months(today().replace(day=1), 1)
        if not need.next_review or need.next_review <= today():
            need.next_review = add_months(today(), 1)
        elif need.next_review.strftime('%Y-%m') == today().strftime('%Y-%m'):
            need.next_review = add_months(need.next_review, 1)
        need.buy_requested = False
    elif payload.action == 'request':
        if need.archived:
            raise HTTPException(409, 'Pulihkan kebutuhan terlebih dahulu')
        need.buy_requested, need.paused, need.snoozed_until = True, False, None
    elif payload.action == 'cancel_request':
        need.buy_requested = False
    elif payload.action == 'archive':
        need.archived = True
    elif payload.action == 'restore':
        need.archived = False
    need.version += 1
    await db.commit()
    return await one(need, db)


def fingerprint(need_id, product_id, payload):
    return hashlib.sha256((str(need_id) + ':' + str(product_id) + ':' + payload.model_dump_json(exclude={'request_id'})).encode()).hexdigest()


async def repeated(payload, digest, user, db):
    event = await db.scalar(select(StockEvent).where(StockEvent.user_id == user.id, StockEvent.request_id == payload.request_id))
    if event and event.request_hash != digest:
        raise HTTPException(409, 'Permintaan ini sudah dipakai untuk perubahan lain')
    return event is not None


async def product_for(need, product_id, db):
    product = await db.scalar(select(StockProduct).where(StockProduct.id == product_id, StockProduct.need_id == need.id))
    if product is None:
        raise HTTPException(404, 'Produk tidak ditemukan')
    return product


def event_row(need, product, payload, digest, kind, active_delta, reserve_delta, **extra):
    return StockEvent(user_id=need.user_id, product_id=product.id, kind=kind, event_date=extra.pop('event_date', today()),
        quantity=extra.pop('quantity', 0), active_delta=active_delta, reserve_delta=reserve_delta,
        brand=product.brand, variant=product.variant, request_id=payload.request_id, request_hash=digest, **extra)


async def save_product(need_id, product_id, payload, user, db):
    need = await owned(need_id, user, db)
    digest = fingerprint(need_id, product_id, payload)
    if await repeated(payload, digest, user, db):
        return await one(need, db)
    if need.archived:
        raise HTTPException(409, 'Pulihkan kebutuhan sebelum mengubah produk')
    if payload.opened_on and payload.opened_on > today():
        raise HTTPException(422, 'Tanggal mulai dipakai tidak boleh di masa depan')
    if product_id:
        product = await product_for(need, product_id, db)
        version(product, payload.version)
        before = product.active_count, product.reserve_count
        product.version += 1
    else:
        product = StockProduct(id=uuid4(), need_id=need.id, version=1)
        before = 0, 0
        db.add(product)
    for key, value in payload.model_dump(exclude={'request_id', 'version'}).items():
        setattr(product, key, value)
    await db.flush()
    db.add(event_row(need, product, payload, digest, 'adjust', product.active_count - before[0], product.reserve_count - before[1]))
    need.version += 1
    await db.commit()
    return await one(need, db)


async def use_product(need_id, product_id, payload, user, db):
    need = await owned(need_id, user, db)
    digest = fingerprint(need_id, product_id, payload)
    if await repeated(payload, digest, user, db):
        return await one(need, db)
    product = await product_for(need, product_id, db)
    version(product, payload.version)
    if need.archived or product.archived or payload.event_date > today():
        raise HTTPException(422, 'Produk/tanggal tidak tersedia untuk pemakaian')
    before = product.active_count, product.reserve_count
    if payload.action == 'open':
        if product.reserve_count == 0:
            raise HTTPException(409, 'Tidak ada kemasan cadangan')
        if product.active_count >= 10000:
            raise HTTPException(422, 'Jumlah kemasan melampaui batas')
        product.active_count += 1
        product.reserve_count -= 1
        product.opened_on = payload.event_date
        product.near_empty = False
    elif payload.action == 'finish':
        if product.active_count == 0:
            raise HTTPException(409, 'Tidak ada kemasan sedang dipakai')
        product.active_count -= 1
        product.near_empty = False
        if payload.open_next and product.reserve_count:
            product.reserve_count -= 1
            product.active_count += 1
            product.opened_on = payload.event_date
        elif not product.active_count:
            product.opened_on = None
    else:
        if not product.active_count:
            raise HTTPException(409, 'Belum ada kemasan sedang dipakai')
        product.near_empty = payload.action == 'near_empty'
    db.add(event_row(need, product, payload, digest, payload.action if payload.action in ('open', 'finish') else 'adjust', product.active_count-before[0], product.reserve_count-before[1], event_date=payload.event_date))
    product.version += 1
    need.version += 1
    await db.commit()
    return await one(need, db)


async def purchase(need_id, product_id, payload, user, db):
    need = await owned(need_id, user, db)
    digest = fingerprint(need_id, product_id, payload)
    if await repeated(payload, digest, user, db):
        return await one(need, db)
    product = await product_for(need, product_id, db)
    version(product, payload.version)
    if need.archived or product.archived or payload.purchase_date > today():
        raise HTTPException(422, 'Produk/tanggal tidak tersedia untuk pembelian')
    if product.reserve_count + payload.quantity > 10000:
        raise HTTPException(422, 'Jumlah stok melampaui batas')
    ledger = None
    if payload.record_expense:
        source = await bank_label(payload.source_bank_id, user.id, db)
        ledger = LedgerTransaction(id=uuid4(), user_id=user.id, kind='expense',
            category={'health': 'health', 'consumption': 'food', 'beauty': 'shopping'}[need.category],
            description=('Stok · ' + need.name + ' · ' + product.brand)[:200],
            amount=payload.amount, transaction_date=payload.purchase_date, source_bank_id=payload.source_bank_id,
            source_label=source, destination_label='', notes=payload.notes)
        db.add(ledger)
        await db.flush()
    product.reserve_count += payload.quantity
    product.version += 1
    need.version += 1
    need.buy_requested = False
    need.snoozed_until = None
    if need.mode == 'monthly' and (not need.next_review or need.next_review <= payload.purchase_date):
        need.next_review = add_months(payload.purchase_date, 1)
    db.add(event_row(need, product, payload, digest, 'purchase', 0, payload.quantity,
        quantity=payload.quantity, event_date=payload.purchase_date, amount=payload.amount, store=payload.store,
        notes=payload.notes, transaction_id=ledger.id if ledger else None))
    await db.commit()
    return await one(need, db)


async def history(need_id, user, db):
    await owned(need_id, user, db, lock=False)
    rows = (await db.execute(select(StockEvent, LedgerTransaction.voided_at).join(StockProduct, StockProduct.id == StockEvent.product_id)
        .outerjoin(LedgerTransaction, LedgerTransaction.id == StockEvent.transaction_id)
        .where(StockProduct.need_id == need_id).order_by(StockEvent.event_date.desc(), StockEvent.created_at.desc(), StockEvent.id).limit(100))).all()
    return [fields(row, 'id product_id kind event_date quantity active_delta reserve_delta brand variant amount store notes transaction_id') | {'ExpenseVoided': bool(voided)} for row, voided in rows]
