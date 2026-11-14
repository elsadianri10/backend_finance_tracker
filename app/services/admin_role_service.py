from typing import Any
from fastapi import HTTPException
from sqlalchemy import select,func
from app.models import User,UserAdminAudit
from app.services.access_service import require_admin,is_admin
from app.config.admin_settings import is_owner_email

def user_output(user):return {'Id':user.id,'Email':user.email,'Name':user.name,'Active':user.is_active,'AdminF':user.admin_f,'OwnerAdmin':is_owner_email(user.email)}
async def change(target_id,payload,actor,db) -> dict[str, Any]:
    require_admin(actor)
    # Serialize role changes; check the actor again after acquiring these locks.
    await db.scalars(select(User).where(User.admin_f==1,User.is_active.is_(True)).order_by(User.id).with_for_update())
    current_actor=await db.scalar(select(User).where(User.id==actor.id).execution_options(populate_existing=True))
    require_admin(current_actor)
    target=await db.scalar(select(User).where(User.id==target_id).with_for_update().execution_options(populate_existing=True))
    if target is None:raise HTTPException(404,'Akun tidak ditemukan')
    if target.admin_f!=payload.expected_admin_f:raise HTTPException(409,'Hak admin sudah berubah. Muat ulang sebelum menyimpan.')
    if payload.admin_f==1 and not target.is_active:raise HTTPException(409,'Akun nonaktif tidak dapat dijadikan admin')
    if payload.admin_f==0 and is_owner_email(target.email):raise HTTPException(409,'Hak admin pemilik utama tidak dapat dicabut dari aplikasi')
    if target.admin_f==payload.admin_f:return user_output(target)
    if payload.admin_f==0:
        count=await db.scalar(select(func.count()).select_from(User).where(User.admin_f==1,User.is_active.is_(True)))
        if target.is_active and count<=1:raise HTTPException(409,'Minimal satu admin aktif harus dipertahankan')
    db.add(UserAdminAudit(user_id=target.id,actor_id=current_actor.id,previous_f=target.admin_f,admin_f=payload.admin_f,reason=payload.reason))
    target.admin_f=payload.admin_f
    await db.commit();return user_output(target)
async def history(target_id,actor,db):
    require_admin(actor)
    rows=(await db.execute(select(UserAdminAudit,User.email).outerjoin(User,User.id==UserAdminAudit.actor_id).where(UserAdminAudit.user_id==target_id).order_by(UserAdminAudit.created_at.desc(),UserAdminAudit.id.desc()).limit(30))).all()
    return [{'Id':row.id,'AdminF':row.admin_f,'PreviousF':row.previous_f,'Reason':row.reason,'CreatedAt':row.created_at,'ActorEmail':email} for row,email in rows]
