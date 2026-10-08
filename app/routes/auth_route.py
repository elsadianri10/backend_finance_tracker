from fastapi import APIRouter, Depends, Response
from app.controllers.auth_controller import get_current_user, login
from app.models.user_model import User
from app.schemas.auth_schema import LoginResponse, UserResponse

router = APIRouter()
router.add_api_route("/google", login, methods=["POST"], response_model=LoginResponse)


@router.get("/me", response_model=UserResponse)
async def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return user
