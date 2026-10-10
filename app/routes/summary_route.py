from fastapi import APIRouter, Depends, Query, Response
from app.controllers import summary_controller as controller
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user


router = APIRouter(tags=['Ringkasan Keuangan'])


@router.get('/summary')
async def get_summary(
    response: Response,
    month: str = Query(pattern='^20\\d{2}-(0[1-9]|1[0-2])$'),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await controller.get_summary(response=response, month=month, user=user, db=db)
