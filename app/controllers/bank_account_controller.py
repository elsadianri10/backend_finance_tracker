from uuid import UUID
from fastapi import Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.bank_account_schema import BankAccountCreate, BankAccountUpdate
from app.services import bank_account_service as service


async def platforms(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.platforms(db)


async def accounts(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.list_accounts(user.id, db)


async def create(payload: BankAccountCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.create(payload, user.id, db)


async def detail(account_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.detail(account_id, user.id, db)


async def update(account_id: UUID, payload: BankAccountUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.update(account_id, payload, user.id, db)


async def delete(account_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await service.delete(account_id, user.id, db)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
