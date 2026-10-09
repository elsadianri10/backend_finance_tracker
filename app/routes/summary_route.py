from fastapi import APIRouter, Depends, Query, Response
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.services.summary_service import summary

router = APIRouter(tags=['Ringkasan Keuangan'])


@router.get('/summary')
async def get_summary(response: Response, month: str = Query(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),
                      user=Depends(get_current_user), db=Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return await summary(user.id, month, db)
