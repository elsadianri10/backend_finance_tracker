import json
from fastapi import HTTPException
from app.services import subscription_service as service


async def mine(response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    return await service.mine(user, db)


async def checkout(payload, response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    return await service.checkout(payload, user, db)


async def refresh(order_id, response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    return await service.refresh(order_id, user, db)


async def cancel(order_id, response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    return await service.cancel(order_id, user, db)


async def webhook(secret, request, response, db):
    response.headers['Cache-Control'] = 'no-store'
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 32768:
            raise HTTPException(413, 'Payload terlalu besar')
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError()
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(400, 'Payload tidak valid') from exc
    return await service.webhook(secret, payload, db)


async def history(response, user, db, offset, limit):
    response.headers['Cache-Control'] = 'no-store'
    return await service.history(user, db, offset, limit)
