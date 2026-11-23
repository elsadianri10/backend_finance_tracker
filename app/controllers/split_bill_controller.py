from uuid import UUID
from fastapi import Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.models.user_model import User
from app.schemas.split_bill_schema import GroupCreate, GroupUpdate
from app.services import split_bill_service as service
from starlette.concurrency import run_in_threadpool
from app.services.split_bill_pdf import export_pdf


async def list_groups(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.list_groups(user.id, db)


async def create(payload: GroupCreate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.save(payload, user.id, db)


async def detail(group_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.response(await service.owned(group_id, user.id, db), db)


async def export(group_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await service.report(group_id, user.id, db)
    content = await run_in_threadpool(export_pdf, group)
    return Response(content, media_type='application/pdf', headers={'Cache-Control': 'no-store', 'Content-Disposition': f'attachment; filename="split-bill-{group_id}.pdf"'})


async def update(group_id: UUID, payload: GroupUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await service.save(payload, user.id, db, group_id)


async def delete(group_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await service.delete_group(group_id, user.id, db)
    return Response(status_code=204, headers={'Cache-Control': 'no-store'})


async def share(group_id, action, response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    operation = {'GET': service.share_status, 'POST': service.create_share, 'DELETE': service.revoke_share}[action]
    return await operation(group_id, user.id, db)


async def shared(token, response, db):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return await service.shared(token, db)
