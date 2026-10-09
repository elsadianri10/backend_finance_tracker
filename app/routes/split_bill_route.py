from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.split_bill_schema import GroupCreate, GroupUpdate
from app.services import split_bill_service as service
from starlette.concurrency import run_in_threadpool
from app.services.split_bill_pdf import export_pdf

router = APIRouter(prefix='/split-bills', tags=['Split Bill'])


@router.get('')
async def list_groups(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.list_groups(user.id, db)


@router.post('', status_code=201)
async def create(payload: GroupCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.save(payload, user.id, db)


@router.get('/{group_id}')
async def detail(group_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.response(await service.owned(group_id, user.id, db), db)


@router.get('/{group_id}/export')
async def export(group_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await service.response(await service.owned(group_id, user.id, db), db)
    content = await run_in_threadpool(export_pdf, group)
    return Response(content, media_type='application/pdf', headers={'Cache-Control': 'no-store', 'Content-Disposition': f'attachment; filename="split-bill-{group_id}.pdf"'})


@router.patch('/{group_id}')
async def update(group_id: UUID, payload: GroupUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.save(payload, user.id, db, group_id)


@router.delete('/{group_id}', status_code=204)
async def delete(group_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.delete(await service.owned(group_id, user.id, db, True))
    await db.commit()
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})

