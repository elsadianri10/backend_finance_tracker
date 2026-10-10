from fastapi import APIRouter, Depends, Response
from app.controllers import auth_controller as controller
from app.controllers.auth_controller import get_current_user
from app.schemas.auth_schema import LoginResponse, UserResponse, GoogleLoginRequest
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.models.user_model import User


router = APIRouter()


@router.post('/google', response_model=LoginResponse)
async def login(
    payload: GoogleLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    return await controller.login(payload=payload, response=response, db=db)


@router.get('/me', response_model=UserResponse)
async def me(response: Response, user: User = Depends(get_current_user)):
    return await controller.me(response=response, user=user)
