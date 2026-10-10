from fastapi import APIRouter, Depends, Response
from app.controllers import split_bill_controller as controller
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.split_bill_schema import GroupCreate, GroupUpdate
from uuid import UUID


router = APIRouter(prefix='/split-bills', tags=['Split Bill'])


@router.get('')
async def list_groups(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_groups(response=response, user=user, db=db)


@router.post('', status_code=201)
async def create(
    payload: GroupCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create(payload=payload, response=response, user=user, db=db)


@router.get('/{group_id}')
async def detail(
    group_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.detail(group_id=group_id, response=response, user=user, db=db)


@router.get('/{group_id}/export')
async def export(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.export(group_id=group_id, user=user, db=db)


@router.patch('/{group_id}')
async def update(
    group_id: UUID,
    payload: GroupUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update(group_id=group_id, payload=payload, response=response, user=user, db=db)


@router.delete('/{group_id}', status_code=204)
async def delete(
    group_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.delete(group_id=group_id, user=user, db=db)
