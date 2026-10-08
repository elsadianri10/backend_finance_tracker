from uuid import UUID

from fastapi import Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.billing_schema import BillingAccountCreate, BillingAccountUpdate
from app.services import billing_service


async def platforms(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await billing_service.list_platforms(db)


async def add_account(payload: BillingAccountCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await billing_service.create_account(payload, user.id, db)


async def accounts(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await billing_service.list_accounts(user.id, db)


async def account(account_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await billing_service.get_account(account_id, user.id, db)


async def update_account(account_id: UUID, payload: BillingAccountUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await billing_service.update_account(account_id, payload, user.id, db)


async def delete_account(account_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await billing_service.delete_account(account_id, user.id, db)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
