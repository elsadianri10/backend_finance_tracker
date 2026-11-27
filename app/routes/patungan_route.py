from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers.patungan_controller import execute
from app.controllers.routine_controller import month_pattern
from app.schemas.patungan_schema import MemberInput, MemberUpdate, ReceiptInput, SubscriptionInput, WaiverInput
from app.services import patungan_service as service

router = APIRouter(prefix='/patungan', tags=['Patungan Langganan'])


@router.get('')
async def groups(response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return await execute(service.groups, response, user, db)


@router.post('', status_code=201)
async def create(payload: SubscriptionInput, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return await execute(service.create_group, response, user, db, payload)


@router.get('/transactions')
async def transactions(response: Response, month: str = Query(pattern=month_pattern), user=Depends(get_current_user), db=Depends(get_db)):
    return await execute(service.transactions, response, user, db, month)


@router.get('/{group_id}')
async def detail(group_id: UUID, response: Response, year: int = Query(ge=2000, le=2099), user=Depends(get_current_user), db=Depends(get_db)):
    return await execute(service.detail, response, user, db, group_id, year)


@router.post('/{group_id}/members', status_code=201)
async def create_member(group_id: UUID, payload: MemberInput, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return await execute(service.create_member, response, user, db, group_id, payload)


@router.patch('/members/{member_id}')
async def update_member(member_id: UUID, payload: MemberUpdate, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return await execute(service.update_member, response, user, db, member_id, payload)


@router.put('/members/{member_id}/waiver', status_code=204)
async def set_waiver(member_id: UUID, payload: WaiverInput, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    await execute(service.set_waiver, response, user, db, member_id, payload)


@router.post('/members/{member_id}/payments', status_code=204)
async def create_payment(member_id: UUID, payload: ReceiptInput, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    await execute(service.create_payment, response, user, db, member_id, payload)


@router.delete('/members/{member_id}/payments/{payment_id}', status_code=204)
async def detach_payment(member_id: UUID, payment_id: UUID, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    await execute(service.detach_payment, response, user, db, member_id, payment_id)
