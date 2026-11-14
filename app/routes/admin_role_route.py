from uuid import UUID
from fastapi import APIRouter,Depends,Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_config import get_db
from app.controllers.auth_controller import get_current_user
from app.controllers.admin_auth_controller import get_current_admin
from app.models import User
from app.schemas.admin_role_schema import AdminRoleChange
from app.controllers import admin_role_controller as controller
router=APIRouter(tags=['Admin Pengguna'])
@router.patch('/admin/users/{target_id}/role')
async def change(target_id:UUID,payload:AdminRoleChange,response:Response,user:User=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
    return await controller.change(target_id,payload,response,user,db)
@router.get('/admin/users/{target_id}/role-history')
async def history(target_id:UUID,response:Response,user:User=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
    return await controller.history(target_id,response,user,db)
