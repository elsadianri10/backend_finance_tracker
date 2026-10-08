from uuid import UUID
from fastapi import Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.models.user_model import User
from app.schemas.billing_transaction_schema import TransactionCreate, LastAmountUpdate
from app.services import billing_transaction_service as service
from app.controllers.auth_controller import get_current_user


async def create(account_id: UUID, payload: TransactionCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.create(account_id, payload, user.id, db)


async def list_transactions(account_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.list_transactions(account_id, user.id, db)


async def detail(transaction_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.detail(transaction_id, user.id, db)


async def mark_paid(transaction_id: UUID, installment_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.mark_paid(transaction_id, installment_id, user.id, db)


async def update_last(transaction_id: UUID, payload: LastAmountUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.update_last(transaction_id, payload.amount, user.id, db)


async def update_subscription(transaction_id: UUID, payload: LastAmountUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.update_subscription(transaction_id, payload.amount, user.id, db)


async def stop_subscription(transaction_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.stop_subscription(transaction_id, user.id, db)


async def delete_subscription(transaction_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await service.delete_subscription(transaction_id, user.id, db)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
