from fastapi import APIRouter, Depends, Response
from app.controllers import debt_controller as controller
from app.schemas.debt_schema import DebtResponse, DebtCreate, PaymentCreate, InstallmentsUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from uuid import UUID


router = APIRouter(prefix='/debts', tags=['Debts & Receivables'])


@router.get('', response_model=list[DebtResponse])
async def list_debts(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_debts(response=response, user=user, db=db)


@router.post('', response_model=DebtResponse, status_code=201)
async def create(
    payload: DebtCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create(payload=payload, response=response, user=user, db=db)


@router.get('/{debt_id}', response_model=DebtResponse)
async def detail(
    debt_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.detail(debt_id=debt_id, response=response, user=user, db=db)


@router.patch('/{debt_id}', response_model=DebtResponse)
async def update(
    debt_id: UUID,
    payload: DebtCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update(debt_id=debt_id, payload=payload, response=response, user=user, db=db)


@router.delete('/{debt_id}', status_code=204)
async def delete(
    debt_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.delete(debt_id=debt_id, user=user, db=db)


@router.post('/{debt_id}/payments', response_model=DebtResponse, status_code=201)
async def pay(
    debt_id: UUID,
    payload: PaymentCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.pay(debt_id=debt_id, payload=payload, response=response, user=user, db=db)


@router.patch('/{debt_id}/installments', response_model=DebtResponse)
async def update_installments(
    debt_id: UUID,
    payload: InstallmentsUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_installments(
        debt_id=debt_id,
        payload=payload,
        response=response,
        user=user,
        db=db,
    )
