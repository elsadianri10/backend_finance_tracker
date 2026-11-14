from fastapi import Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import bearer
from fastapi.security import HTTPAuthorizationCredentials
from app.services import admin_auth_service as service
from app.services.auth_service import user_from_access_token
from app.services.access_service import require_admin
from app.schemas.auth_schema import UserResponse
async def get_current_admin(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:AsyncSession=Depends(get_db)):
    if credentials is None:raise HTTPException(401,'Admin login required')
    user=await user_from_access_token(credentials.credentials,db,kind='admin_access')
    require_admin(user);return user
async def login(payload,response,db):
    response.headers['Cache-Control']='no-store';return await service.login(payload.id_token,db)
async def options(response,token,db,purpose):
    response.headers['Cache-Control']='no-store';return await service.options(token,db,purpose)
async def verify(response,token,db,payload,purpose):
    response.headers['Cache-Control']='no-store';result=await service.verify(token,payload,db,purpose)
    result['User']=UserResponse.model_validate(result['User']).model_dump(by_alias=True,mode='json');return result
async def recover(response,token,db,payload):
    response.headers['Cache-Control']='no-store';result=await service.recover(token,payload.code,db)
    result['User']=UserResponse.model_validate(result['User']).model_dump(by_alias=True,mode='json');return result
