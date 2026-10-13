from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers import passkey_controller as controller
from app.schemas.passkey_schema import CredentialInput, RecoveryInput

router = APIRouter(prefix='/passkeys', tags=['Passkey'])


@router.get('')
async def state(response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.state(response, token, db)


@router.post('/register/options')
async def register_options(response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.options(response, token, db, 'REGISTER')


@router.post('/register/verify')
async def register_verify(payload: CredentialInput, response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.verify(response, token, db, payload, 'REGISTER')


@router.post('/login/options')
async def login_options(response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.options(response, token, db, 'LOGIN')


@router.post('/login/verify')
async def login_verify(payload: CredentialInput, response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.verify(response, token, db, payload, 'LOGIN')


@router.post('/manage/options')
async def manage_options(response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.options(response, token, db, 'MANAGE')


@router.post('/manage/verify')
async def manage_verify(payload: CredentialInput, response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.verify(response, token, db, payload, 'MANAGE')


@router.post('/recovery')
async def recover(payload: RecoveryInput, response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.recover(response, token, db, payload)


@router.post('/recovery-codes')
async def regenerate(response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.regenerate(response, token, db)


@router.delete('/{key_id}')
async def remove(key_id: UUID, response: Response, token: str = Depends(controller.token), db: AsyncSession = Depends(get_db)):
    return await controller.remove(response, token, db, key_id)
