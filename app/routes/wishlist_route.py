from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers import wishlist_controller as controller
from app.models import User
from app.schemas.wishlist_schema import WishlistInput, GroupInput, ItemInput

router = APIRouter(prefix='/wishlists', tags=['Wishlist'])


@router.get('')
async def lists(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('list_owned', response, user, db)


@router.post('', status_code=201)
async def create(payload: WishlistInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('create', response, payload, user, db)


@router.get('/shared/{token}')
async def public(token: str, response: Response, user: User | None = Depends(controller.optional_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('public', response, token, user, db)


@router.post('/shared/{token}/items/{item_id}/reservation')
async def reserve_shared(token: str, item_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('reserve', response, None, token, item_id, False, user, db)


@router.delete('/shared/{token}/items/{item_id}/reservation')
async def cancel_shared(token: str, item_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('reserve', response, None, token, item_id, True, user, db)


@router.patch('/{list_id}')
async def update(list_id: UUID, payload: WishlistInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('update', response, list_id, payload, user, db)


@router.delete('/{list_id}')
async def remove(list_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('remove', response, list_id, user, db)


@router.post('/{list_id}/groups', status_code=201)
async def group(list_id: UUID, payload: GroupInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('add_group', response, list_id, payload, user, db)


@router.patch('/{list_id}/groups/{group_id}')
async def group_update(list_id: UUID, group_id: UUID, payload: GroupInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('change_group', response, list_id, group_id, payload, user, db)


@router.delete('/{list_id}/groups/{group_id}')
async def group_remove(list_id: UUID, group_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('change_group', response, list_id, group_id, None, user, db)


@router.post('/{list_id}/items', status_code=201)
async def item(list_id: UUID, payload: ItemInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('save_item', response, list_id, None, payload, user, db)


@router.patch('/{list_id}/items/{item_id}')
async def item_update(list_id: UUID, item_id: UUID, payload: ItemInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('save_item', response, list_id, item_id, payload, user, db)


@router.delete('/{list_id}/items/{item_id}')
async def item_remove(list_id: UUID, item_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('remove_item', response, list_id, item_id, user, db)


@router.post('/{list_id}/share')
async def share(list_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('share', response, list_id, user, db)


@router.delete('/{list_id}/share')
async def revoke(list_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('revoke', response, list_id, user, db)


@router.post('/{list_id}/items/{item_id}/reservation')
async def reserve(list_id: UUID, item_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('reserve', response, list_id, None, item_id, False, user, db)


@router.delete('/{list_id}/items/{item_id}/reservation')
async def cancel(list_id: UUID, item_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('reserve', response, list_id, None, item_id, True, user, db)
