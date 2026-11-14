from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers.admin_auth_controller import get_current_admin
from app.controllers import access_controller as controller
from app.models.user_model import User
from app.schemas.access_schema import AccessChange

router = APIRouter(tags=['Paket dan Akses'])


@router.get('/access/me')
async def mine(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.mine(response, user, db)


@router.get('/admin/access/users')
async def users(response: Response, search: str = Query('', max_length=160), offset: int = Query(0, ge=0),
                limit: int = Query(25, ge=1, le=50), user: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await controller.users(response, user, db, search, offset, limit)


@router.patch('/admin/access/users/{target_id}')
async def change(target_id: UUID, payload: AccessChange, response: Response,
                 user: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await controller.change(target_id, payload, response, user, db)


@router.get('/admin/access/users/{target_id}/history')
async def history(target_id: UUID, response: Response, user: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await controller.history(target_id, response, user, db)


@router.get('/access/usage')
async def usage(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.usage(response, user, db)


@router.get('/plans')
def plans(response: Response):
    return controller.plans(response)
