from uuid import UUID
from fastapi import Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.debt_schema import DebtCreate, PaymentCreate, InstallmentsUpdate
from app.services import debt_service as service


async def list_debts(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.list_debts(user.id, db)


async def create(payload: DebtCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.create(payload, user.id, db)


async def detail(debt_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.detail(debt_id, user.id, db)


async def update(debt_id: UUID, payload: DebtCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.update(debt_id, payload, user.id, db)


async def delete(debt_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await service.delete(debt_id, user.id, db)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


async def pay(debt_id: UUID, payload: PaymentCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.add_payment(debt_id, payload, user.id, db)


async def update_installments(debt_id: UUID, payload: InstallmentsUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.update_installments(debt_id, payload, user.id, db)
