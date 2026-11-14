"""Subscription lifecycle. Gateway responses, never browser callbacks, grant paid access."""
import calendar
import hmac
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4
from typing import Any
from fastapi import HTTPException
from sqlalchemy import select
from app.models.user_model import User
from app.models.access_model import AccountAccess
from app.models.subscription_model import SubscriptionOrder, SubscriptionPayment
from app.services import midtrans_service as gateway
from app.services.access_service import now, utc, status

PRICES = {'MONTHLY': 29000, 'ANNUAL': 249000}
CONSENT_VERSION = '2026-11-02'


def add_period(at, plan):
    months = 12 if plan == 'ANNUAL' else 1
    index = at.year * 12 + at.month - 1 + months
    year, month = divmod(index, 12)
    return at.replace(year=year, month=month + 1, day=min(at.day, calendar.monthrange(year, month + 1)[1]))


def provider_date(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone(timedelta(hours=7))).astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(502, 'Tanggal pembayaran tidak valid') from exc


def amount_matches(value, amount):
    try:
        return Decimal(str(value)).is_finite() and Decimal(str(value)) == amount
    except InvalidOperation:
        return False


def order_name(order):
    return 'fto_' + order.id.hex


def renewal_name(order):
    return 'ftr_' + order.id.hex


def output(row):
    return {'Id': row.id, 'Plan': row.plan, 'Amount': row.amount, 'Environment': row.environment,
            'State': row.state, 'CheckoutUrl': row.redirect_url if row.state == 'PENDING' else None,
            'AutoRenew': row.auto_renew, 'RenewalState': row.renewal_state,
            'NextChargeAt': utc(row.next_charge_at), 'CancelRequestedAt': utc(row.cancel_requested_at),
            'CancelledAt': utc(row.cancelled_at), 'CreatedAt': utc(row.created_at)}


async def lock_user(db, user_id):
    await db.scalar(select(User.id).where(User.id == user_id).with_for_update())


async def owned(db, order_id, user):
    await lock_user(db, user.id)
    row = await db.scalar(select(SubscriptionOrder).where(SubscriptionOrder.id == order_id,
        SubscriptionOrder.user_id == user.id).execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, 'Langganan tidak ditemukan')
    if row.environment != gateway.configuration()[0]:
        raise HTTPException(409, 'Langganan berasal dari lingkungan pembayaran berbeda')
    return row


async def mine(user, db):
    mode, _, _, enabled = gateway.configuration()
    rows = list(await db.scalars(select(SubscriptionOrder).where(SubscriptionOrder.user_id == user.id,
        SubscriptionOrder.environment == mode).order_by(SubscriptionOrder.created_at.desc(), SubscriptionOrder.id.desc()).limit(10)))
    return {'Enabled': enabled, 'Environment': mode,
            'AutoRenewEnabled': enabled and os.getenv('MIDTRANS_RECURRING_ENABLED', 'false').lower() == 'true',
            'ConsentVersion': CONSENT_VERSION, 'MonthlyAmount': PRICES['MONTHLY'], 'AnnualAmount': PRICES['ANNUAL'],
            'Orders': [output(row) for row in rows]}


async def checkout(payload, user, db):
    mode, _, origin, enabled = gateway.configuration()
    if not enabled:
        raise HTTPException(503, 'Pembayaran belum tersedia')
    if payload.expected_amount is not None and payload.expected_amount != PRICES[payload.plan]:
        raise HTTPException(409, 'Harga paket berubah. Tinjau ulang pembelian.')
    if payload.auto_renew and os.getenv('MIDTRANS_RECURRING_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Autodebit belum tersedia')
    await lock_user(db, user.id)
    access = await db.get(AccountAccess, user.id)
    if status(access)['Source'] == 'COMPLIMENTARY':
        raise HTTPException(409, 'Akun sudah memiliki Pro gratis aktif')
    previous = await db.scalar(select(SubscriptionOrder).where(SubscriptionOrder.user_id == user.id,
        SubscriptionOrder.request_id == payload.request_id))
    if previous:
        if (previous.plan, previous.auto_renew, previous.environment) != (payload.plan, payload.auto_renew, mode):
            raise HTTPException(409, 'Permintaan pembayaran sudah dipakai untuk pilihan berbeda')
        return output(previous)
    all_orders = list(await db.scalars(select(SubscriptionOrder).where(SubscriptionOrder.user_id == user.id)
        .order_by(SubscriptionOrder.created_at, SubscriptionOrder.id)))
    if any(row.state in {'PENDING', 'REVIEW'} or row.renewal_state in {'PENDING', 'CREATING', 'ACTIVE', 'REVIEW'}
           for row in all_orders):
        raise HTTPException(409, 'Selesaikan pembayaran atau batalkan perpanjangan sebelumnya dahulu')
    row = SubscriptionOrder(id=uuid4(), user_id=user.id, request_id=payload.request_id, plan=payload.plan,
        amount=PRICES[payload.plan], environment=mode, auto_renew=payload.auto_renew,
        consented_at=now() if payload.auto_renew else None, consent_version=CONSENT_VERSION if payload.auto_renew else None,
        state='REVIEW', renewal_state='PENDING' if payload.auto_renew else 'NONE',
        access_before=all_orders[0].access_before if all_orders else (utc(access.subscription_until) if access else None))
    db.add(row)
    # Persist identity before calling a non-transactional external service. An ambiguous timeout is never retried as a new charge.
    await db.commit()
    body = {'transaction_details': {'order_id': order_name(row), 'gross_amount': row.amount},
        'customer_details': {'first_name': user.name[:100], 'email': user.email},
        'item_details': [{'id': row.plan, 'price': row.amount, 'quantity': 1, 'name': 'Finance Tracker Pro ' + row.plan}],
        'callbacks': {'finish': origin + '/profile#pro-plans'},
        'expiry': {'duration': 30, 'unit': 'minute'}, 'page_expiry': {'duration': 30, 'unit': 'minute'}}
    if row.auto_renew:
        body.update({'enabled_payments': ['gopay', 'credit_card'], 'user_id': str(user.id),
            'gopay': {'tokenization': True}, 'credit_card': {'secure': True, 'save_card': True},
            'recurring': {'required': True}})
    data = await gateway.call('POST', '/snap/v1/transactions', body, snap=True)
    row.redirect_url = gateway.checkout_url(data.get('redirect_url'))
    row.state = 'PENDING'
    await db.commit()
    return output(row)


async def recalculate(db, user_id):
    orders = list(await db.scalars(select(SubscriptionOrder).where(SubscriptionOrder.user_id == user_id)
        .order_by(SubscriptionOrder.created_at, SubscriptionOrder.id)))
    by_id = {row.id: row for row in orders}
    access = await db.get(AccountAccess, user_id)
    if access is None:
        access = AccountAccess(user_id=user_id, version=1)
        db.add(access)
    cursor = utc(orders[0].access_before) if orders else None
    trial_end = utc(access.trial_until)
    payments = list(await db.scalars(select(SubscriptionPayment).join(SubscriptionOrder)
        .where(SubscriptionOrder.user_id == user_id).order_by(SubscriptionPayment.paid_at, SubscriptionPayment.transaction_id)))
    for payment in payments:
        if payment.state != 'PAID':
            continue
        begin = max(value for value in (cursor, trial_end, utc(payment.paid_at)) if value is not None)
        payment.period_start = begin
        cursor = payment.period_end = add_period(begin, by_id[payment.order_id].plan)
    access.subscription_plan = 'PRO' if cursor else 'FREE'
    access.subscription_until = cursor
    access.version = (access.version or 0) + 1
    await db.flush()
    return cursor


async def apply_payment(row, data, db, *, recurring=False):
    if not amount_matches(data.get('gross_amount'), row.amount) or data.get('currency', 'IDR') != 'IDR':
        raise HTTPException(409, 'Nominal atau mata uang pembayaran tidak cocok')
    provider_order = gateway.identifier(data.get('order_id'))
    if not recurring and provider_order != order_name(row):
        raise HTTPException(409, 'Order pembayaran tidak cocok')
    state = data.get('transaction_status')
    successful = state in {'settlement', 'capture'} and data.get('fraud_status', 'accept') == 'accept'
    refunded = state in {'refund', 'chargeback'}
    transaction_id = gateway.identifier(data.get('transaction_id'))
    payment = await db.scalar(select(SubscriptionPayment).where(SubscriptionPayment.environment == row.environment,
        SubscriptionPayment.transaction_id == transaction_id))
    if payment and payment.order_id != row.id:
        raise HTTPException(409, 'Transaksi terhubung ke order berbeda')
    if successful or refunded:
        if payment is None:
            paid_at = provider_date(data.get('settlement_time') or data.get('transaction_time'))
            payment = SubscriptionPayment(id=uuid4(), order_id=row.id, environment=row.environment,
                transaction_id=transaction_id, provider_order_id=provider_order, amount=row.amount,
                state='REFUNDED' if refunded else 'PAID', paid_at=paid_at, period_start=paid_at, period_end=paid_at)
            db.add(payment)
        elif refunded:
            payment.state = 'REFUNDED'
        # A stale success notification cannot resurrect a refunded payment.
        if not recurring:
            row.state = 'REFUNDED' if payment.state == 'REFUNDED' else 'PAID'
        await db.flush()
        await recalculate(db, row.user_id)
        if refunded and row.auto_renew:
            row.cancel_requested_at = row.cancel_requested_at or now()
    elif not recurring and row.state not in {'PAID', 'REFUNDED'}:
        row.state = {'expire': 'EXPIRED', 'cancel': 'CANCELLED', 'deny': 'DENIED'}.get(state, row.state)
        if row.state in {'EXPIRED', 'CANCELLED', 'DENIED'}:
            row.renewal_state = 'CANCELLED' if row.auto_renew else 'NONE'
    await db.commit()


async def setup_renewal(row, data, db):
    if not row.auto_renew or row.state != 'PAID' or row.cancel_requested_at or row.renewal_state != 'PENDING':
        return
    method = data.get('payment_type')
    token = data.get('saved_token_id') if method == 'credit_card' else None
    account_id = None
    if method == 'gopay':
        account_id = data.get('account_id') or (data.get('gopay') or {}).get('account_id')
        if not account_id:
            row.renewal_state = 'FAILED'; await db.commit(); return
        account = await gateway.call('GET', '/v2/pay/account/' + gateway.identifier(account_id))
        options = (account.get('metadata') or {}).get('payment_options') or []
        token = next((option.get('token') for option in options if option.get('name') == 'GOPAY_WALLET' and option.get('active') is True), None)
    if not token or method not in {'credit_card', 'gopay'}:
        row.renewal_state = 'FAILED'; await db.commit(); return
    access = await db.get(AccountAccess, row.user_id)
    start = utc(access.subscription_until) if access else None
    if not start or start <= now():
        row.renewal_state = 'FAILED'; await db.commit(); return
    row.next_charge_at = start
    row.renewal_state = 'CREATING'
    row.setup_attempted_at = now()
    await db.commit()
    body = {'name': renewal_name(row), 'amount': str(row.amount), 'currency': 'IDR', 'payment_type': method,
        'token': token, 'schedule': {'interval': 12 if row.plan == 'ANNUAL' else 1, 'interval_unit': 'month',
        'start_time': start.strftime('%Y-%m-%d %H:%M:%S +0000')},
        'retry_schedule': {'interval': 1, 'interval_unit': 'day', 'max_interval': 0}}
    if account_id:
        body['gopay'] = {'account_id': account_id}
    try:
        result = await gateway.call('POST', '/v1/subscriptions', body, idempotency=str(row.id))
        provider_id = gateway.identifier(result.get('id'))
    except HTTPException:
        await lock_user(db, row.user_id)
        await db.refresh(row)
        if not row.provider_subscription_id:
            row.renewal_state = 'REVIEW'
            await db.commit()
        raise
    await lock_user(db, row.user_id)
    await db.refresh(row)
    row.provider_subscription_id = provider_id
    if row.renewal_state != 'CANCELLED':
        row.renewal_state = 'ACTIVE'
    await db.commit()
    if row.cancel_requested_at and row.renewal_state != 'CANCELLED':
        await cancel_provider(row, db)


async def cancel_provider(row, db):
    if row.provider_subscription_id:
        await gateway.call('POST', '/v1/subscriptions/' + gateway.identifier(row.provider_subscription_id) + '/cancel')
        row.renewal_state = 'CANCELLED'; row.cancelled_at = now(); row.next_charge_at = None
    elif row.setup_attempted_at:
        row.renewal_state = 'REVIEW'
    else:
        row.renewal_state = 'CANCELLED'; row.cancelled_at = now(); row.next_charge_at = None
    await db.commit()


async def cancel(order_id, user, db):
    row = await owned(db, order_id, user)
    row.cancel_requested_at = row.cancel_requested_at or now()
    await db.commit()
    if row.renewal_state != 'CANCELLED':
        await cancel_provider(row, db)
    return output(row)


async def refresh(order_id, user, db) -> dict[str, Any]:
    row = await owned(db, order_id, user)
    try:
        data = await gateway.call('GET', '/v2/' + order_name(row) + '/status')
    except HTTPException as exc:
        # A Snap page that never selected a method has no transaction status. Its configured expiry is 30 minutes.
        if exc.status_code == 404 and row.state in {'PENDING', 'REVIEW'} and utc(row.created_at) + timedelta(minutes=35) < now():
            row.state = 'EXPIRED'; row.renewal_state = 'CANCELLED' if row.auto_renew else 'NONE'
            await db.commit()
            return output(row)
        raise
    await apply_payment(row, data, db)
    await lock_user(db, row.user_id)
    await db.refresh(row)
    existing_provider = row.provider_subscription_id
    await setup_renewal(row, data, db)
    if existing_provider:
        verified = await gateway.call('GET', '/v1/subscriptions/' + gateway.identifier(row.provider_subscription_id))
        if verified.get('name') != renewal_name(row) or not amount_matches(verified.get('amount'), row.amount) or verified.get('currency') != 'IDR':
            raise HTTPException(409, 'Langganan tidak cocok')
        if row.renewal_state != 'CANCELLED':
            row.renewal_state = 'ACTIVE' if verified.get('status') == 'active' else 'FAILED'
            value = (verified.get('schedule') or {}).get('next_execution_at')
            row.next_charge_at = provider_date(value) if value and row.renewal_state == 'ACTIVE' else None
        known = set(await db.scalars(select(SubscriptionPayment.transaction_id).where(SubscriptionPayment.order_id == row.id)))
        for transaction_id in [value for value in verified.get('transaction_ids', []) if value not in known][:2]:
            transaction = await gateway.call('GET', '/v2/' + gateway.identifier(transaction_id) + '/status')
            if transaction.get('transaction_id') != transaction_id:
                raise HTTPException(409, 'Identitas transaksi tidak cocok')
            await apply_payment(row, transaction, db, recurring=True)
        await db.commit()
    if row.cancel_requested_at and row.renewal_state != 'CANCELLED':
        await cancel_provider(row, db)
    return output(row)


async def webhook(secret, payload, db):
    configured = os.getenv('MIDTRANS_WEBHOOK_TOKEN', '')
    if not configured or not hmac.compare_digest(secret, configured):
        raise HTTPException(404, 'Tidak ditemukan')
    mode = gateway.configuration()[0]
    # Recurring callbacks do not carry the ordinary signature_key. Read subscription and transaction over authenticated API.
    subscription = payload.get('subscription') or (payload if payload.get('id') and payload.get('name') else None)
    if subscription is not None and not isinstance(subscription, dict):
        raise HTTPException(422, 'Payload langganan tidak valid')
    if subscription:
        provider_id = gateway.identifier(subscription.get('id'))
        verified = await gateway.call('GET', '/v1/subscriptions/' + provider_id)
        name = verified.get('name', '')
        try:
            order_id = UUID(hex=name.removeprefix('ftr_')) if name.startswith('ftr_') else None
        except (ValueError, AttributeError):
            order_id = None
        row = await db.get(SubscriptionOrder, order_id) if order_id else None
        if not row or row.environment != mode or not row.setup_attempted_at:
            raise HTTPException(404, 'Langganan tidak ditemukan')
        await lock_user(db, row.user_id); await db.refresh(row)
        if verified.get('name') != renewal_name(row) or not amount_matches(verified.get('amount'), row.amount) or verified.get('currency') != 'IDR' or (row.provider_subscription_id and row.provider_subscription_id != provider_id):
            raise HTTPException(409, 'Langganan tidak cocok')
        row.provider_subscription_id = provider_id
        if row.renewal_state != 'CANCELLED':
            row.renewal_state = 'ACTIVE' if verified.get('status') == 'active' else 'FAILED'
            value = (verified.get('schedule') or {}).get('next_execution_at')
            row.next_charge_at = provider_date(value) if value and row.renewal_state == 'ACTIVE' else None
        transaction = payload.get('transaction') or {}
        if not isinstance(transaction, dict):
            raise HTTPException(422, 'Payload transaksi tidak valid')
        transaction_id = transaction.get('transaction_id')
        if transaction_id:
            transaction_id = gateway.identifier(transaction_id)
            known_payment = await db.scalar(select(SubscriptionPayment.id).where(SubscriptionPayment.order_id == row.id,
                SubscriptionPayment.environment == mode, SubscriptionPayment.transaction_id == transaction_id))
            if transaction_id not in verified.get('transaction_ids', []) and known_payment is None:
                if verified.get('status') == 'inactive':
                    await db.commit()
                else:
                    raise HTTPException(409, 'Transaksi bukan milik langganan')
            else:
                data = await gateway.call('GET', '/v2/' + transaction_id + '/status')
                if data.get('transaction_id') != transaction_id:
                    raise HTTPException(409, 'Identitas transaksi tidak cocok')
                await apply_payment(row, data, db, recurring=True)
        else:
            await db.commit()
        if row.cancel_requested_at and row.renewal_state != 'CANCELLED':
            await cancel_provider(row, db)
        return {'Received': True}
    provider_order = gateway.identifier(payload.get('order_id'))
    row = None
    if provider_order.startswith('fto_'):
        try:
            row = await db.get(SubscriptionOrder, UUID(hex=provider_order[4:]))
        except ValueError:
            pass
    # Refunds and ordinary charge notifications may arrive through the payment URL instead.
    if row is None and provider_order.startswith('ftr_') and len(provider_order) > 36:
        try:
            parent = await db.get(SubscriptionOrder, UUID(hex=provider_order[4:36]))
        except ValueError:
            parent = None
        if parent and parent.provider_subscription_id and parent.environment == mode:
            return await webhook(secret, {'subscription': {'id': parent.provider_subscription_id},
                'transaction': {'transaction_id': payload.get('transaction_id')}}, db)
    if row is None or row.environment != mode:
        return {'Received': True}
    await lock_user(db, row.user_id); await db.refresh(row)
    data = await gateway.call('GET', '/v2/' + provider_order + '/status')
    await apply_payment(row, data, db)
    await lock_user(db, row.user_id); await db.refresh(row)
    await setup_renewal(row, data, db)
    if row.cancel_requested_at and row.renewal_state != 'CANCELLED':
        await cancel_provider(row, db)
    return {'Received': True}


async def history(user, db, offset=0, limit=10):
    from sqlalchemy import func
    mode = os.getenv('MIDTRANS_ENVIRONMENT', 'sandbox')
    if mode not in {'sandbox','production'}:
        raise HTTPException(503, 'Konfigurasi lingkungan pembayaran tidak valid')
    predicate = (SubscriptionOrder.user_id == user.id, SubscriptionOrder.environment == mode)
    total = await db.scalar(select(func.count()).select_from(SubscriptionOrder).where(*predicate)) or 0
    orders = list(await db.scalars(select(SubscriptionOrder).where(*predicate).order_by(SubscriptionOrder.created_at.desc(), SubscriptionOrder.id.desc()).offset(offset).limit(limit)))
    ids = [row.id for row in orders]
    payments = list(await db.scalars(select(SubscriptionPayment).where(SubscriptionPayment.order_id.in_(ids)).order_by(SubscriptionPayment.paid_at.desc(), SubscriptionPayment.id.desc()))) if ids else []
    return {'Items': [output(row) | {'Payments': [{'Id': payment.id, 'Amount': payment.amount, 'State': payment.state,
        'PaidAt': utc(payment.paid_at), 'PeriodStart': utc(payment.period_start), 'PeriodEnd': utc(payment.period_end)}
        for payment in payments if payment.order_id == row.id]} for row in orders], 'Total': total,
        'NextOffset': offset+limit if offset+limit<total else None}
