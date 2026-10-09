from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.schemas.routine_schema import RoutineInput, RoutineUpdate, PaymentInput, TransactionInput, ImportInput
from app.services import routine_service as service

router = APIRouter(tags=['Pengeluaran Rutin & Transaksi'])
month_query = Query(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$')


def no_store(response: Response):
    response.headers['Cache-Control'] = 'no-store'


@router.get('/routine/options')
async def options(response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.options(user.id, db)


@router.get('/routine')
async def plans(response: Response, month: str = month_query, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.list_plans(user.id, month, db)


@router.post('/routine', status_code=201)
async def create(payload: RoutineInput, response: Response, month: str = month_query, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.save_plan(payload, user.id, month, db)


@router.patch('/routine/{plan_id}')
async def update(plan_id: UUID, payload: RoutineUpdate, response: Response, month: str = month_query, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.save_plan(payload, user.id, month, db, plan_id)


@router.post('/routine/{plan_id}/payments', status_code=201)
async def pay(plan_id: UUID, payload: PaymentInput, response: Response, month: str = month_query, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.pay(plan_id, payload, user.id, month, db)


@router.delete('/routine/{plan_id}/payments/{payment_id}')
async def undo(plan_id: UUID, payment_id: UUID, response: Response, month: str = month_query, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.undo(plan_id, payment_id, user.id, month, db)


@router.delete('/routine/{plan_id}', status_code=204)
async def remove(plan_id: UUID, user=Depends(get_current_user), db=Depends(get_db)):
    await service.remove_plan(plan_id, user.id, db)
    return Response(status_code=204, headers={'Cache-Control':'no-store'})


@router.get('/transactions')
async def transactions(response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.list_transactions(user.id, db)


@router.post('/transactions', status_code=201)
async def transaction_create(payload: TransactionInput, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.save_transaction(payload, user.id, db)


@router.patch('/transactions/{item_id}')
async def transaction_update(item_id: UUID, payload: TransactionInput, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.save_transaction(payload, user.id, db, item_id)


@router.delete('/transactions/{item_id}', status_code=204)
async def transaction_remove(item_id: UUID, user=Depends(get_current_user), db=Depends(get_db)):
    await service.remove_transaction(item_id, user.id, db)
    return Response(status_code=204, headers={'Cache-Control':'no-store'})


@router.post('/transactions/import')
async def transaction_import(payload: ImportInput, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    no_store(response)
    return await service.import_transactions(payload, user.id, db)
