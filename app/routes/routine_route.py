from fastapi import APIRouter, Depends, Response
from app.controllers import routine_controller as controller
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.schemas.routine_schema import (
    RoutineInput,
    RoutineUpdate,
    PaymentInput,
    TransactionInput,
    ImportInput,
)
from uuid import UUID


router = APIRouter(tags=['Pengeluaran Rutin & Transaksi'])


month_query = controller.month_query


@router.get('/routine/options')
async def options(response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return await controller.options(response=response, user=user, db=db)


@router.get('/routine')
async def plans(
    response: Response,
    month: str = month_query,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.plans(response=response, month=month, user=user, db=db)


@router.post('/routine', status_code=201)
async def create(
    payload: RoutineInput,
    response: Response,
    month: str = month_query,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.create(payload=payload, response=response, month=month, user=user, db=db)


@router.patch('/routine/{plan_id}')
async def update(
    plan_id: UUID,
    payload: RoutineUpdate,
    response: Response,
    month: str = month_query,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.update(
        plan_id=plan_id,
        payload=payload,
        response=response,
        month=month,
        user=user,
        db=db,
    )


@router.post('/routine/{plan_id}/payments', status_code=201)
async def pay(
    plan_id: UUID,
    payload: PaymentInput,
    response: Response,
    month: str = month_query,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.pay(
        plan_id=plan_id,
        payload=payload,
        response=response,
        month=month,
        user=user,
        db=db,
    )


@router.delete('/routine/{plan_id}/payments/{payment_id}')
async def undo(
    plan_id: UUID,
    payment_id: UUID,
    response: Response,
    month: str = month_query,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.undo(
        plan_id=plan_id,
        payment_id=payment_id,
        response=response,
        month=month,
        user=user,
        db=db,
    )


@router.delete('/routine/{plan_id}', status_code=204)
async def remove(plan_id: UUID, user=Depends(get_current_user), db=Depends(get_db)):
    return await controller.remove(plan_id=plan_id, user=user, db=db)


@router.get('/transactions')
async def transactions(response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return await controller.transactions(response=response, user=user, db=db)


@router.post('/transactions', status_code=201)
async def transaction_create(
    payload: TransactionInput,
    response: Response,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.transaction_create(payload=payload, response=response, user=user, db=db)


@router.patch('/transactions/{item_id}')
async def transaction_update(
    item_id: UUID,
    payload: TransactionInput,
    response: Response,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.transaction_update(
        item_id=item_id,
        payload=payload,
        response=response,
        user=user,
        db=db,
    )


@router.delete('/transactions/{item_id}', status_code=204)
async def transaction_remove(item_id: UUID, user=Depends(get_current_user), db=Depends(get_db)):
    return await controller.transaction_remove(item_id=item_id, user=user, db=db)


@router.post('/transactions/import')
async def transaction_import(
    payload: ImportInput,
    response: Response,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.transaction_import(payload=payload, response=response, user=user, db=db)
