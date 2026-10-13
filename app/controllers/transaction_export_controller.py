from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Response
from app.models import User
from app.schemas.transaction_export_schema import TransactionExportInput
from app.services import transaction_export_service as service


async def export(payload: TransactionExportInput, format: Literal['pdf', 'xlsx'], user: User, db: AsyncSession):
    content, media_type = await service.export(payload, format, user, db)
    return Response(content, media_type=media_type, headers={
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': f'attachment; filename="finance-transactions-{payload.month}.{format}"',
    })
