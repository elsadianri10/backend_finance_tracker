from fastapi import APIRouter, Depends, Response
from app.controllers import savings_controller as controller
from app.schemas.savings_schema import SavingResponse, SavingCreate, MovementCreate
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from uuid import UUID


router = APIRouter(prefix='/savings', tags=['Savings'])


@router.get('', response_model=list[SavingResponse])
async def list_savings(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_savings(response=response, user=user, db=db)


@router.post('', response_model=SavingResponse, status_code=201)
async def create(
    payload: SavingCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create(payload=payload, response=response, user=user, db=db)


@router.get('/{saving_id}', response_model=SavingResponse)
async def detail(
    saving_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.detail(saving_id=saving_id, response=response, user=user, db=db)


@router.patch('/{saving_id}', response_model=SavingResponse)
async def update(
    saving_id: UUID,
    payload: SavingCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update(saving_id=saving_id, payload=payload, response=response, user=user, db=db)


@router.delete('/{saving_id}', status_code=204)
async def delete(
    saving_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.delete(saving_id=saving_id, user=user, db=db)


@router.post('/{saving_id}/movements', response_model=SavingResponse, status_code=201)
async def move(
    saving_id: UUID,
    payload: MovementCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.move(saving_id=saving_id, payload=payload, response=response, user=user, db=db)
