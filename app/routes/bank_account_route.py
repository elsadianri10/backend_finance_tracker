from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.bank_account_schema import BankAccountCreate, BankAccountUpdate, BankAccountResponse, WalletProviderResponse
from app.services import bank_account_service as service

router = APIRouter(prefix="/bank-accounts", tags=["My Bank Account"])


@router.get("/platforms", response_model=list[WalletProviderResponse])
async def platforms(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.platforms(db)


@router.get("", response_model=list[BankAccountResponse])
async def accounts(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.list_accounts(user.id, db)


@router.post("", response_model=BankAccountResponse, status_code=201)
async def create(payload: BankAccountCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.create(payload, user.id, db)


@router.get("/{account_id}", response_model=BankAccountResponse)
async def detail(account_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.detail(account_id, user.id, db)


@router.patch("/{account_id}", response_model=BankAccountResponse)
async def update(account_id: UUID, payload: BankAccountUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return await service.update(account_id, payload, user.id, db)


@router.delete("/{account_id}", status_code=204)
async def delete(account_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await service.delete(account_id, user.id, db)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
