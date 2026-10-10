from fastapi import APIRouter, Depends, Response
from app.controllers import bank_account_controller as controller
from app.schemas.bank_account_schema import (
    BankAccountResponse,
    WalletProviderResponse,
    BankAccountCreate,
    BankAccountUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from uuid import UUID


router = APIRouter(prefix='/bank-accounts', tags=['My Bank Account'])


@router.get('/platforms', response_model=list[WalletProviderResponse])
async def platforms(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.platforms(response=response, user=user, db=db)


@router.get('', response_model=list[BankAccountResponse])
async def accounts(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.accounts(response=response, user=user, db=db)


@router.post('', response_model=BankAccountResponse, status_code=201)
async def create(
    payload: BankAccountCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create(payload=payload, response=response, user=user, db=db)


@router.get('/{account_id}', response_model=BankAccountResponse)
async def detail(
    account_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.detail(account_id=account_id, response=response, user=user, db=db)


@router.patch('/{account_id}', response_model=BankAccountResponse)
async def update(
    account_id: UUID,
    payload: BankAccountUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update(
        account_id=account_id,
        payload=payload,
        response=response,
        user=user,
        db=db,
    )


@router.delete('/{account_id}', status_code=204)
async def delete(
    account_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.delete(account_id=account_id, user=user, db=db)
