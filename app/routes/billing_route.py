from fastapi import APIRouter, Depends, Response
from app.controllers import billing_controller as controller
from app.schemas.billing_schema import (
    BillingAccountResponse,
    BillingPlatformResponse,
    BillingAccountCreate,
    BillingAccountUpdate,
)
from app.controllers import billing_transaction_controller as transactions
from app.schemas.billing_transaction_schema import (
    TransactionResponse,
    TransactionCreate,
    LastAmountUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from uuid import UUID


router = APIRouter(prefix='/billing', tags=['Billing'])


@router.get('/platforms', response_model=list[BillingPlatformResponse])
async def platforms(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.platforms(response=response, user=user, db=db)


@router.post('/accounts', response_model=BillingAccountResponse, status_code=201)
async def add_account(
    payload: BillingAccountCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.add_account(payload=payload, response=response, user=user, db=db)


@router.get('/accounts', response_model=list[BillingAccountResponse])
async def accounts(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.accounts(response=response, user=user, db=db)


@router.get('/accounts/{account_id}', response_model=BillingAccountResponse)
async def account(
    account_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.account(account_id=account_id, response=response, user=user, db=db)


@router.patch('/accounts/{account_id}', response_model=BillingAccountResponse)
async def update_account(
    account_id: UUID,
    payload: BillingAccountUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_account(
        account_id=account_id,
        payload=payload,
        response=response,
        user=user,
        db=db,
    )


@router.delete('/accounts/{account_id}', status_code=204)
async def delete_account(
    account_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.delete_account(account_id=account_id, user=user, db=db)


@router.post('/accounts/{account_id}/transactions', response_model=TransactionResponse, status_code=201)
async def create(
    account_id: UUID,
    payload: TransactionCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.create(
        account_id=account_id,
        payload=payload,
        response=response,
        user=user,
        db=db,
    )


@router.get('/accounts/{account_id}/transactions', response_model=list[TransactionResponse])
async def list_transactions(
    account_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.list_transactions(account_id=account_id, response=response, user=user, db=db)


@router.get('/transactions/{transaction_id}', response_model=TransactionResponse)
async def detail(
    transaction_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.detail(transaction_id=transaction_id, response=response, user=user, db=db)


@router.post('/transactions/{transaction_id}/installments/{installment_id}/pay', response_model=TransactionResponse)
async def mark_paid(
    transaction_id: UUID,
    installment_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.mark_paid(
        transaction_id=transaction_id,
        installment_id=installment_id,
        response=response,
        user=user,
        db=db,
    )


@router.patch('/transactions/{transaction_id}/last-amount', response_model=TransactionResponse)
async def update_last(
    transaction_id: UUID,
    payload: LastAmountUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.update_last(
        transaction_id=transaction_id,
        payload=payload,
        response=response,
        user=user,
        db=db,
    )


@router.patch('/transactions/{transaction_id}/subscription-amount', response_model=TransactionResponse)
async def update_subscription(
    transaction_id: UUID,
    payload: LastAmountUpdate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.update_subscription(
        transaction_id=transaction_id,
        payload=payload,
        response=response,
        user=user,
        db=db,
    )


@router.post('/transactions/{transaction_id}/stop', response_model=TransactionResponse)
async def stop_subscription(
    transaction_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.stop_subscription(
        transaction_id=transaction_id,
        response=response,
        user=user,
        db=db,
    )


@router.delete('/transactions/{transaction_id}', status_code=204)
async def delete_subscription(
    transaction_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await transactions.delete_subscription(transaction_id=transaction_id, user=user, db=db)
