from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers import subscription_controller as controller
from app.models.user_model import User
from app.schemas.subscription_schema import SubscriptionCheckout

router = APIRouter(prefix='/subscriptions', tags=['Langganan Pro'])


@router.get('/me')
async def mine(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.mine(response, user, db)


@router.post('/checkout')
async def checkout(payload: SubscriptionCheckout, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.checkout(payload, response, user, db)


@router.post('/orders/{order_id}/refresh')
async def refresh(order_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.refresh(order_id, response, user, db)


@router.post('/orders/{order_id}/cancel-renewal')
async def cancel(order_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.cancel(order_id, response, user, db)


@router.post('/webhooks/{secret}')
async def webhook(secret: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    return await controller.webhook(secret, request, response, db)


@router.get('/history')
async def history(response: Response, offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=20),
                  user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.history(response, user, db, offset, limit)
