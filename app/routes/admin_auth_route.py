from fastapi import APIRouter,Depends,Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers import admin_auth_controller as controller
from app.controllers.passkey_controller import token
from app.schemas.auth_schema import GoogleLoginRequest,PendingLoginResponse,UserResponse
from app.schemas.passkey_schema import CredentialInput,RecoveryInput
from app.models import User
router=APIRouter(prefix='/admin/auth',tags=['Login Portal Admin'])
@router.post('/google',response_model=PendingLoginResponse)
async def login(payload:GoogleLoginRequest,response:Response,db:AsyncSession=Depends(get_db)):
    return await controller.login(payload,response,db)
@router.get('/me',response_model=UserResponse)
async def me(response:Response,user:User=Depends(controller.get_current_admin)):
    response.headers['Cache-Control']='no-store';return user
@router.post('/passkeys/register/options')
async def register_options(response:Response,credential:str=Depends(token),db:AsyncSession=Depends(get_db)):
    return await controller.options(response,credential,db,'REGISTER')
@router.post('/passkeys/register/verify')
async def register_verify(payload:CredentialInput,response:Response,credential:str=Depends(token),db:AsyncSession=Depends(get_db)):
    return await controller.verify(response,credential,db,payload,'REGISTER')
@router.post('/passkeys/login/options')
async def login_options(response:Response,credential:str=Depends(token),db:AsyncSession=Depends(get_db)):
    return await controller.options(response,credential,db,'LOGIN')
@router.post('/passkeys/login/verify')
async def login_verify(payload:CredentialInput,response:Response,credential:str=Depends(token),db:AsyncSession=Depends(get_db)):
    return await controller.verify(response,credential,db,payload,'LOGIN')
@router.post('/passkeys/recovery')
async def recover(payload:RecoveryInput,response:Response,credential:str=Depends(token),db:AsyncSession=Depends(get_db)):
    return await controller.recover(response,credential,db,payload)
