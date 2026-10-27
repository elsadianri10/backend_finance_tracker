from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers import stock_controller as controller
from app.models import User
from app.schemas.stock_schema import NeedInput, NeedAction, ProductInput, ProductAction, PurchaseInput, DeleteNeedInput, DeleteProductInput, ProductReplenishmentInput

router = APIRouter(prefix='/stock-needs', tags=['Stok Kebutuhan'])


@router.get('')
async def listed(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('listed', response, user, db)


@router.post('', status_code=201)
async def create(payload: NeedInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('save_need', response, None, payload, user, db)


@router.patch('/{need_id}')
async def update(need_id: UUID, payload: NeedInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('save_need', response, need_id, payload, user, db)


@router.post('/{need_id}/actions')
async def control(need_id: UUID, payload: NeedAction, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('control', response, need_id, payload, user, db)


@router.delete('/{need_id}')
async def remove(need_id: UUID, payload: DeleteNeedInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('remove', response, need_id, payload, user, db)


@router.get('/{need_id}/history')
async def history(need_id: UUID, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('history', response, need_id, user, db)


@router.post('/{need_id}/products', status_code=201)
async def product(need_id: UUID, payload: ProductInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('save_product', response, need_id, None, payload, user, db)


@router.patch('/{need_id}/products/{product_id}')
async def product_update(need_id: UUID, product_id: UUID, payload: ProductInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('save_product', response, need_id, product_id, payload, user, db)


@router.post('/{need_id}/products/{product_id}/actions')
async def usage(need_id: UUID, product_id: UUID, payload: ProductAction, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('use_product', response, need_id, product_id, payload, user, db)


@router.delete('/{need_id}/products/{product_id}')
async def product_remove(need_id: UUID, product_id: UUID, payload: DeleteProductInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('remove_product', response, need_id, product_id, payload, user, db)


@router.post('/{need_id}/products/{product_id}/purchases', status_code=201)
async def purchase(need_id: UUID, product_id: UUID, payload: PurchaseInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('purchase', response, need_id, product_id, payload, user, db)


@router.post('/{need_id}/products/{product_id}/replenishment')
async def replenishment(need_id: UUID, product_id: UUID, payload: ProductReplenishmentInput, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await controller.execute('product_replenishment', response, need_id, product_id, payload, user, db)
