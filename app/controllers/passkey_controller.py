from uuid import UUID
from fastapi import Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.services import passkey_service as service
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth_schema import UserResponse
from app.schemas.passkey_schema import CredentialInput, RecoveryInput

bearer = HTTPBearer(auto_error=False)


def token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if credentials is None:
        raise HTTPException(401, 'Bearer token is required')
    return credentials.credentials


async def state(response: Response, token: str, db: AsyncSession):
    response.headers['Cache-Control'] = 'no-store'
    return await service.state(token, db)


async def options(response: Response, token: str, db: AsyncSession, purpose: str):
    response.headers['Cache-Control'] = 'no-store'
    return await service.options(token, db, purpose)


async def verify(response: Response, token: str, db: AsyncSession, payload: CredentialInput, purpose: str):
    response.headers['Cache-Control'] = 'no-store'
    result = await service.verify(token, payload, db, purpose)
    result['User'] = UserResponse.model_validate(result['User']).model_dump(by_alias=True, mode='json')
    return result


async def recover(response: Response, token: str, db: AsyncSession, payload: RecoveryInput):
    response.headers['Cache-Control'] = 'no-store'
    result = await service.recover(token, payload.code, db)
    result['User'] = UserResponse.model_validate(result['User']).model_dump(by_alias=True, mode='json')
    return result


async def remove(response: Response, token: str, db: AsyncSession, key_id: UUID):
    response.headers['Cache-Control'] = 'no-store'
    result = await service.remove(token, key_id, db)
    result['User'] = UserResponse.model_validate(result['User']).model_dump(by_alias=True, mode='json')
    return result


async def regenerate(response: Response, token: str, db: AsyncSession):
    response.headers['Cache-Control'] = 'no-store'
    result = await service.regenerate(token, db)
    result['User'] = UserResponse.model_validate(result['User']).model_dump(by_alias=True, mode='json')
    return result
