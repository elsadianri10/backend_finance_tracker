from typing import Literal
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers import transaction_export_controller as controller
from app.models import User
from app.schemas.transaction_export_schema import TransactionExportInput

router = APIRouter(tags=['Ekspor Transaksi'])


@router.post('/transactions/export/{format}')
async def export(
    format: Literal['pdf', 'xlsx'], payload: TransactionExportInput,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await controller.export(payload, format, user, db)
