from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.db_config import get_db
from app.controllers import budget_controller as controller
from app.controllers.auth_controller import get_current_user
from app.models import User
from app.schemas.budget_schema import BudgetInput, BudgetUpdate

router = APIRouter(prefix='/budgeting', tags=['Budgeting'])


@router.get('')
async def listing(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.listing(response, user, db)


@router.post('', status_code=201)
async def create(payload: BudgetInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.save(payload, response, user, db)


@router.patch('/{budget_id}')
async def update(budget_id: UUID, payload: BudgetUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.save(payload, response, user, db, budget_id)


@router.delete('/{budget_id}', status_code=204)
async def delete(budget_id: UUID, response: Response, version: int = Query(gt=0), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await controller.delete(budget_id, version, response, user, db)
