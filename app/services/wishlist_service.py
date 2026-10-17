import hashlib
import secrets
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.services import wishlist_image_service as images
from app.models import User
from app.models.wishlist_model import Wishlist, WishlistGroup, WishlistItem, WishlistPhoto, WishlistReservation

GIFTABLE = {'things', 'consumables', 'games', 'food'}


def photo_url(photo, share_token=None):
    if not photo.blob_url:
        return photo.url
    # A different object at the same position must refresh an already-mounted img.
    version = hashlib.sha256(photo.blob_url.encode()).hexdigest()[:16]
    return photo.url + '?v=' + version + ('&share=' + share_token if share_token else '')


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


async def output(lists, viewer_id, db, share_token=None):
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
                value.update(Photos=[photo_url(p, share_token) for p in photos if p.item_id == item.id], Reserved=bool(reservation), Mine=mine,
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
    blobs = await stored_photos(db, list_id=row.id)
    await db.delete(row)
    await db.commit()
    await images.cleanup(blobs)
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
    blobs = await stored_photos(db, group_id=group.id) if payload is None else []
    if payload is None:
        await db.delete(group)
    else:
        group.name = payload.name
    await db.commit()
    await images.cleanup(blobs)
    return (await output([row], user.id, db))[0]


async def save_item(list_id, item_id, payload, user, db, uploads=None):
    row = await owned(list_id, user, db)
    group = await db.scalar(select(WishlistGroup).where(WishlistGroup.id == payload.group_id, WishlistGroup.wishlist_id == row.id))
    if group is None:
        raise HTTPException(404, 'Grup tidak ditemukan')
    item = await db.scalar(select(WishlistItem).join(WishlistGroup).where(WishlistItem.id == item_id, WishlistGroup.wishlist_id == row.id)) if item_id else None
    if item_id and item is None:
        raise HTTPException(404, 'Barang tidak ditemukan')
    old_photos = list(await db.scalars(select(WishlistPhoto).where(WishlistPhoto.item_id == item.id))) if item else []
    retained = {photo_url(p): p.blob_url for p in old_photos if p.blob_url}
    if any(url.startswith('/') and url not in retained for url in payload.photos):
        raise HTTPException(422, 'Referensi foto tidak valid untuk barang ini')
    if len(payload.photos) + len(uploads or []) > 6:
        raise HTTPException(422, 'Maksimal enam foto termasuk link dan unggahan')
    # Validate every file before writing any object or changing existing rows.
    normalized = [images.normalize(data) for data in (uploads or [])]
    new_blobs = []
    try:
        if item is None:
            item = WishlistItem()
            db.add(item)
        for key, value in payload.model_dump(exclude={'photos'}).items():
            setattr(item, key, value)
        await db.flush()
        for data in normalized:
            new_blobs.append(await images.put(item.id, data))
        entries = [(url, retained.get(url)) for url in payload.photos] + [('', url) for url in new_blobs]
        await db.execute(delete(WishlistPhoto).where(WishlistPhoto.item_id == item.id))
        db.add_all([WishlistPhoto(item_id=item.id, position=index,
            url=f'/api/wishlists/images/{item.id}/{index}' if blob else url, blob_url=blob)
            for index, (url, blob) in enumerate(entries)])
        if item.status != 'wanted':
            await db.execute(delete(WishlistReservation).where(WishlistReservation.item_id == item.id))
        await db.commit()
    except Exception:
        await db.rollback()
        await images.cleanup(new_blobs)
        raise
    used = {blob for _, blob in entries if blob}
    await images.cleanup([p.blob_url for p in old_photos if p.blob_url and p.blob_url not in used])
    return (await output([row], user.id, db))[0]


async def photo(item_id, position, token, user, db):
    result = (await db.execute(select(WishlistPhoto, Wishlist, WishlistItem.status)
        .join(WishlistItem, WishlistItem.id == WishlistPhoto.item_id)
        .join(WishlistGroup, WishlistGroup.id == WishlistItem.group_id)
        .join(Wishlist, Wishlist.id == WishlistGroup.wishlist_id)
        .where(WishlistPhoto.item_id == item_id, WishlistPhoto.position == position))).first()
    if result is None:
        raise HTTPException(404, 'Foto tidak ditemukan')
    image, row, status = result
    owner = user is not None and user.id == row.user_id
    allowed = token and row.share_hash and secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(), row.share_hash)
    if not image.blob_url or (not owner and (not allowed or status == 'archived')):
        raise HTTPException(404, 'Foto tidak ditemukan')
    return await images.read(image.blob_url)


async def stored_photos(db, list_id=None, group_id=None, item_id=None):
    query = select(WishlistPhoto.blob_url).join(WishlistItem).join(WishlistGroup)
    if list_id:
        query = query.where(WishlistGroup.wishlist_id == list_id)
    if group_id:
        query = query.where(WishlistGroup.id == group_id)
    if item_id:
        query = query.where(WishlistItem.id == item_id)
    return [url for url in await db.scalars(query) if url]



async def remove_item(list_id, item_id, user, db):
    row = await owned(list_id, user, db)
    item = await db.scalar(select(WishlistItem).join(WishlistGroup).where(WishlistItem.id == item_id, WishlistGroup.wishlist_id == row.id))
    if item is None:
        raise HTTPException(404, 'Barang tidak ditemukan')
    blobs = await stored_photos(db, item_id=item.id)
    await db.delete(item)
    await db.commit()
    await images.cleanup(blobs)
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
    return (await output([row], user.id if user else None, db, token))[0]


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
    return (await output([row], user.id, db, token))[0]
