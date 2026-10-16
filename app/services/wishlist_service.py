import hashlib
import secrets
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.models import User
from app.models.wishlist_model import Wishlist, WishlistGroup, WishlistItem, WishlistPhoto, WishlistReservation

GIFTABLE = {'things', 'consumables', 'games', 'food'}


async def owned(list_id, user, db):
    row = await db.scalar(select(Wishlist).where(Wishlist.id == list_id, Wishlist.user_id == user.id).with_for_update())
    if row is None:
        raise HTTPException(404, 'Wishlist tidak ditemukan')
    return row


async def shared(token, db):
    row = await db.scalar(select(Wishlist).where(Wishlist.share_hash == hashlib.sha256(token.encode()).hexdigest()).with_for_update())
    if row is None:
        raise HTTPException(404, 'Link Wishlist tidak tersedia atau sudah dicabut')
    return row


async def output(lists, viewer_id, db):
    groups = list(await db.scalars(select(WishlistGroup).where(WishlistGroup.wishlist_id.in_([r.id for r in lists])).order_by(WishlistGroup.name, WishlistGroup.id)))
    items = list(await db.scalars(select(WishlistItem).where(WishlistItem.group_id.in_([g.id for g in groups])).order_by(WishlistItem.name, WishlistItem.id)))
    photos = list(await db.scalars(select(WishlistPhoto).where(WishlistPhoto.item_id.in_([i.id for i in items])).order_by(WishlistPhoto.position)))
    reservations = dict((r.item_id, (r, name)) for r, name in (await db.execute(select(WishlistReservation, User.name).join(User, User.id == WishlistReservation.user_id).where(WishlistReservation.item_id.in_([i.id for i in items])))).all())
    result = []
    for row in lists:
        owner = viewer_id == row.user_id
        rendered_groups = []
        for group in (g for g in groups if g.wishlist_id == row.id):
            rendered = []
            for item in (i for i in items if i.group_id == group.id and (owner or i.status != 'archived')):
                reservation = reservations.get(item.id)
                mine = bool(reservation and reservation[0].user_id == viewer_id)
                value = {''.join(p.title() for p in key.split('_')): getattr(item, key) for key in (
                    'id', 'group_id', 'name', 'platform', 'brand', 'model', 'color', 'capacity', 'year', 'plate', 'country', 'province', 'city', 'notes', 'link', 'price', 'priority', 'status')}
                value.update(Photos=[p.url for p in photos if p.item_id == item.id], Reserved=bool(reservation), Mine=mine,
                    ReservedBy=reservation[1] if reservation and (owner or mine) else None)
                rendered.append(value)
            rendered_groups.append({'Id': group.id, 'Name': group.name, 'Items': rendered,
                'Subtotal': sum(int(i['Price'] or 0) for i in rendered if i['Status'] not in ('fulfilled', 'archived'))})
        result.append({'Id': row.id, 'Name': row.name, 'Kind': row.kind, 'Owner': owner,
            'Shared': bool(row.share_hash), 'CanReserve': row.kind in GIFTABLE and row.share_mode == 'reserve',
            'Groups': rendered_groups, 'Total': sum(g['Subtotal'] for g in rendered_groups)})
    return result


async def list_owned(user, db):
    rows = list(await db.scalars(select(Wishlist).where(Wishlist.user_id == user.id).order_by(Wishlist.name, Wishlist.id)))
    return await output(rows, user.id, db)


async def create(payload, user, db):
    row = Wishlist(user_id=user.id, **payload.model_dump())
    db.add(row)
    await db.flush()
    db.add(WishlistGroup(wishlist_id=row.id, name='Umum'))
    await db.commit()
    return (await output([row], user.id, db))[0]


async def update(list_id, payload, user, db):
    row = await owned(list_id, user, db)
    row.name = payload.name
    row.kind = payload.kind
    if row.kind not in GIFTABLE:
        row.share_mode = 'view'
    await db.commit()
    return (await output([row], user.id, db))[0]


async def remove(list_id, user, db):
    row = await owned(list_id, user, db)
    await db.delete(row)
    await db.commit()
    return {'Ok': True}


async def add_group(list_id, payload, user, db):
    row = await owned(list_id, user, db)
    db.add(WishlistGroup(wishlist_id=row.id, name=payload.name))
    await db.commit()
    return (await output([row], user.id, db))[0]


async def change_group(list_id, group_id, payload, user, db):
    row = await owned(list_id, user, db)
    group = await db.scalar(select(WishlistGroup).where(WishlistGroup.id == group_id, WishlistGroup.wishlist_id == row.id))
    if group is None:
        raise HTTPException(404, 'Grup tidak ditemukan')
    if payload is None:
        await db.delete(group)
    else:
        group.name = payload.name
    await db.commit()
    return (await output([row], user.id, db))[0]


async def save_item(list_id, item_id, payload, user, db):
    row = await owned(list_id, user, db)
    group = await db.scalar(select(WishlistGroup).where(WishlistGroup.id == payload.group_id, WishlistGroup.wishlist_id == row.id))
    if group is None:
        raise HTTPException(404, 'Grup tidak ditemukan')
    item = await db.scalar(select(WishlistItem).join(WishlistGroup).where(WishlistItem.id == item_id, WishlistGroup.wishlist_id == row.id)) if item_id else None
    if item_id and item is None:
        raise HTTPException(404, 'Barang tidak ditemukan')
    if item is None:
        item = WishlistItem()
        db.add(item)
    for key, value in payload.model_dump(exclude={'photos'}).items():
        setattr(item, key, value)
    await db.flush()
    await db.execute(delete(WishlistPhoto).where(WishlistPhoto.item_id == item.id))
    db.add_all([WishlistPhoto(item_id=item.id, position=index, url=url) for index, url in enumerate(payload.photos)])
    if item.status != 'wanted':
        await db.execute(delete(WishlistReservation).where(WishlistReservation.item_id == item.id))
    await db.commit()
    return (await output([row], user.id, db))[0]


async def remove_item(list_id, item_id, user, db):
    row = await owned(list_id, user, db)
    item = await db.scalar(select(WishlistItem).join(WishlistGroup).where(WishlistItem.id == item_id, WishlistGroup.wishlist_id == row.id))
    if item is None:
        raise HTTPException(404, 'Barang tidak ditemukan')
    await db.delete(item)
    await db.commit()
    return (await output([row], user.id, db))[0]


async def share(list_id, user, db):
    row = await owned(list_id, user, db)
    token = secrets.token_urlsafe(32)
    row.share_hash = hashlib.sha256(token.encode()).hexdigest()
    row.share_mode = 'reserve' if row.kind in GIFTABLE else 'view'
    await db.commit()
    return {'Token': token}


async def revoke(list_id, user, db):
    row = await owned(list_id, user, db)
    row.share_hash = None
    await db.commit()
    return (await output([row], user.id, db))[0]


async def public(token, user, db):
    row = await shared(token, db)
    return (await output([row], user.id if user else None, db))[0]


async def reserve(list_id, token, item_id, cancel, user, db):
    row = await shared(token, db) if token else await owned(list_id, user, db)
    owner = row.user_id == user.id
    if not owner and (row.kind not in GIFTABLE or row.share_mode != 'reserve'):
        raise HTTPException(403, 'Wishlist ini hanya dapat dilihat')
    item = await db.scalar(select(WishlistItem).join(WishlistGroup).where(WishlistItem.id == item_id, WishlistGroup.wishlist_id == row.id).with_for_update())
    if item is None:
        raise HTTPException(404, 'Barang tidak ditemukan')
    existing = await db.get(WishlistReservation, item.id)
    if cancel:
        if existing and existing.user_id != user.id and not owner:
            raise HTTPException(403, 'Anda hanya dapat membatalkan reservasi sendiri')
        if existing:
            await db.delete(existing)
    else:
        if item.status != 'wanted':
            raise HTTPException(409, 'Barang tidak tersedia untuk direservasi')
        if existing and existing.user_id != user.id:
            raise HTTPException(409, 'Barang sudah direservasi')
        if existing is None:
            db.add(WishlistReservation(item_id=item.id, user_id=user.id))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, 'Barang sudah direservasi. Muat ulang Wishlist.')
    return (await output([row], user.id, db))[0]
