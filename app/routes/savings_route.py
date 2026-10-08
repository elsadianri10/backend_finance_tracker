from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.savings_schema import SavingCreate, SavingResponse, MovementCreate
from app.services import savings_service as service

router = APIRouter(prefix='/savings', tags=['Savings'])


@router.get('', response_model=list[SavingResponse])
async def list_savings(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.list_savings(user.id, db)


@router.post('', response_model=SavingResponse, status_code=201)
async def create(payload: SavingCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.create(payload, user.id, db)


@router.get('/{saving_id}', response_model=SavingResponse)
async def detail(saving_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.detail(saving_id, user.id, db)


@router.patch('/{saving_id}', response_model=SavingResponse)
async def update(saving_id: UUID, payload: SavingCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.update(saving_id, payload, user.id, db)


@router.delete('/{saving_id}', status_code=204)
async def delete(saving_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await service.delete(saving_id, user.id, db)
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})


@router.post('/{saving_id}/movements', response_model=SavingResponse, status_code=201)
async def move(saving_id: UUID, payload: MovementCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.add_movement(saving_id, payload, user.id, db)
