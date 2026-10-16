from fastapi import Depends, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.services.auth_service import user_from_access_token
from app.services import wishlist_service as service

optional_bearer = HTTPBearer(auto_error=False)


async def optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer), db: AsyncSession = Depends(get_db)):
    return await user_from_access_token(credentials.credentials, db) if credentials else None


async def execute(action, response: Response, *args):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return await getattr(service, action)(*args)
