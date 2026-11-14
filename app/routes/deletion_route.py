from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers.admin_auth_controller import get_current_admin
from app.controllers import deletion_controller as controller
from app.models import User
from app.schemas.deletion_schema import DeletionSubmit,DeletionReview
router=APIRouter(tags=['Penghapusan Akun'])
@router.get('/account/deletion')
async def own(response:Response,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    return await controller.own(response,user,db)
@router.post('/account/deletion',status_code=201)
async def submit(payload:DeletionSubmit,response:Response,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    return await controller.submit(payload,response,user,db)
@router.post('/account/deletion/cancel')
async def cancel(response:Response,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    return await controller.cancel(response,user,db)
@router.get('/admin/deletions')
async def listing(response:Response,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),user:User=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
    return await controller.listing(response,user,db,offset,limit)
@router.post('/admin/deletions/{request_id}')
async def review(request_id:UUID,payload:DeletionReview,response:Response,user:User=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
    return await controller.review(request_id,payload,response,user,db)
