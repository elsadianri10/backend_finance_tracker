from fastapi import Depends, Response, HTTPException
from pydantic import ValidationError
from app.schemas.wishlist_schema import ItemInput
from app.services.wishlist_image_service import MAX_IMAGE_BYTES
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.services.auth_service import user_from_access_token
from app.services import wishlist_service as service

optional_bearer = HTTPBearer(auto_error=False)


async def optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer), db: AsyncSession = Depends(get_db)):
    return await user_from_access_token(credentials.credentials, db) if credentials else None


async def execute(action, response: Response, *args):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return await getattr(service, action)(*args)


async def upload(list_id, item_id, metadata, files, response, user, db):
    try:
        if len(metadata) > 40000:
            raise HTTPException(413, 'Data terlalu besar')
        payload = ItemInput.model_validate_json(metadata)
    except ValidationError:
        raise HTTPException(422, 'Isian Wishlist tidak valid') from None
    if not files or len(payload.photos) + len(files) > 6:
        raise HTTPException(422, 'Maksimal enam foto termasuk link dan unggahan')
    uploads = []
    try:
        for file in files:
            data = await file.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise HTTPException(413, 'Foto terlalu besar. Pilih ulang melalui form upload.')
            uploads.append(data)
    finally:
        for file in files:
            await file.close()
    return await execute('save_item', response, list_id, item_id, payload, user, db, uploads)


async def photo(item_id, position, share, user, db):
    data = await service.photo(item_id, position, share, user, db)
    return Response(data, media_type='image/webp', headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'X-Robots-Tag': 'noindex, nofollow', 'Referrer-Policy': 'no-referrer',
    })
