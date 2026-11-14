"""Admin-portal authentication has distinct JWT purposes from Finance Tracker."""
import jwt
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.config import auth_settings as settings
from app.models import User
from app.services import auth_service,passkey_service
from app.services.access_service import require_admin

PENDING_TYPES=('passkey_pending','passkey_enrollment')
def encode(claims):return jwt.encode(claims,settings.SECRET_KEY,algorithm=settings.ALGORITHM)
async def login(token,db):
    result=await auth_service.google_login(token,db,portal='admin')
    kind='passkey_enrollment' if result['EnrollmentRequired'] else 'passkey_pending'
    claims=auth_service.token_claims(result['PendingToken'],kind)
    claims['type']='admin_'+kind
    return result|{'PendingToken':encode(claims)}
async def pending(token,db,purpose):
    kind='passkey_enrollment' if purpose=='REGISTER' else 'passkey_pending'
    claims=auth_service.token_claims(token,'admin_'+kind)
    user=await db.scalar(select(User).where(User.id==UUID(claims['sub'])).with_for_update())
    if user is None or claims.get('ver',0)!=user.auth_version:raise HTTPException(401,'Sesi admin berakhir')
    require_admin(user)
    # The shared WebAuthn verifier only receives a purpose-limited token in memory.
    # Its general access token is replaced before any response leaves this service.
    claims['type']=kind
    return encode(claims)
async def options(token,db,purpose):
    return await passkey_service.options(await pending(token,db,purpose),db,purpose)
async def verify(token,payload,db,purpose):
    result=await passkey_service.verify(await pending(token,db,purpose),payload,db,purpose)
    user = result['User']
    if not isinstance(user, User):
        raise HTTPException(401, 'Sesi admin tidak valid')
    require_admin(user)
    return auth_service.issue_access(user,'passkey',portal='admin')|{'RecoveryCodes':result.get('RecoveryCodes',[])}
async def recover(token,code,db):
    result=await passkey_service.recover(await pending(token,db,'LOGIN'),code,db)
    user = result['User']
    if not isinstance(user, User):
        raise HTTPException(401, 'Sesi admin tidak valid')
    require_admin(user)
    return auth_service.issue_access(user,'recovery',portal='admin')
