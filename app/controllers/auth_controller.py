from fastapi import Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.models.user_model import User
from app.schemas.auth_schema import GoogleLoginRequest
from app.services.auth_service import google_login, user_from_access_token

bearer = HTTPBearer(auto_error=False)


async def login(payload: GoogleLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await google_login(payload.id_token, db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Bearer token is required", headers={"WWW-Authenticate": "Bearer"})
    return await user_from_access_token(credentials.credentials, db)
