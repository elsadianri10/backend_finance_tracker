"""User-requested deletion, explicitly processed by an administrator."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, delete, func, or_
from app.models import Base, User, AccountDeletion, DeletionBlob, SubscriptionOrder, SubscriptionPayment
from app.services.access_service import require_admin, is_admin

def stamp():return datetime.now(timezone.utc)
def output(row):
    return {'Id':row.id,'Status':row.status,'CreatedAt':row.created_at,'UpdatedAt':row.updated_at,'CompletedAt':row.completed_at}
async def own(user,db):
    row=await db.scalar(select(AccountDeletion).where(AccountDeletion.subject_id==user.id).order_by(AccountDeletion.created_at.desc(),AccountDeletion.id.desc()).limit(1))
    return output(row) if row else None
async def submit(payload,user,db):
    current_user=await db.scalar(select(User).where(User.id==user.id).with_for_update().execution_options(populate_existing=True))
    if is_admin(current_user):raise HTTPException(403,'Akun admin tidak dapat mengajukan penghapusan')
    if payload.confirmation.strip().casefold()!=user.email.casefold():raise HTTPException(422,'Konfirmasi email tidak cocok')
    current=await db.scalar(select(AccountDeletion).where(AccountDeletion.user_id==user.id,AccountDeletion.status.in_(['PENDING','REVIEWING'])).with_for_update())
    if current:return output(current)
    row=AccountDeletion(user_id=user.id,subject_id=user.id,created_at=stamp(),updated_at=stamp());db.add(row);await db.commit();return output(row)
async def cancel(user,db):
    await db.scalar(select(User.id).where(User.id==user.id).with_for_update())
    row=await db.scalar(select(AccountDeletion).where(AccountDeletion.user_id==user.id,AccountDeletion.status.in_(['PENDING','REVIEWING'])).with_for_update())
    if not row:raise HTTPException(409,'Tidak ada permintaan yang dapat dibatalkan')
    row.status='CANCELLED';row.updated_at=stamp();await db.commit();return output(row)
async def listing(admin,db,offset=0,limit=20):
    require_admin(admin)
    rows=(await db.execute(select(AccountDeletion,User).outerjoin(User,User.id==AccountDeletion.user_id).order_by(AccountDeletion.created_at.desc(),AccountDeletion.id.desc()).offset(offset).limit(limit))).all()
    total=await db.scalar(select(func.count()).select_from(AccountDeletion)) or 0
    return {'Items':[output(row)|{'UserName':user.name if user else None,'UserEmail':user.email if user else None} for row,user in rows],'Total':total,'NextOffset':offset+limit if offset+limit<total else None}

def predicates(user_id):
    tables=Base.metadata.tables
    conditions={name:t.c.user_id==user_id for name,t in tables.items() if 'user_id' in t.c and name not in {'account_deletions'}}
    paths={'billing_transactions':('account_id','billing_accounts'),'billing_installments':('transaction_id','billing_transactions'),'debt_installments':('debt_id','debts'),'debt_payments':('debt_id','debts'),'saving_movements':('saving_id','savings'),'routine_payments':('plan_id','routine_plans'),'stock_products':('need_id','stock_needs'),'wishlist_groups':('wishlist_id','wishlists'),'wishlist_items':('group_id','wishlist_groups'),'wishlist_photos':('item_id','wishlist_items'),'subscription_payments':('order_id','subscription_orders')}
    for child,(key,parent) in paths.items():
        conditions[child]=tables[child].c[key].in_(select(tables[parent].c.id).where(conditions[parent]))
    for name in ['split_bill_participants','split_bill_expenses','split_bill_items','split_bill_shares']:
        conditions[name]=tables[name].c.group_id.in_(select(tables['split_bill_groups'].c.id).where(conditions['split_bill_groups']))
    conditions['wishlist_reservations']=or_(conditions['wishlist_reservations'],tables['wishlist_reservations'].c.item_id.in_(select(tables['wishlist_items'].c.id).where(conditions['wishlist_items'])))
    return conditions

async def finish_blobs(row,db):
    from app.services.wishlist_image_service import delete_verified
    row=await db.scalar(select(AccountDeletion).where(AccountDeletion.id==row.id).with_for_update().execution_options(populate_existing=True))
    if row.status=='COMPLETED':return output(row)
    if row.status!='CLEANUP':raise HTTPException(409,'Status pembersihan sudah berubah')
    blobs=list(await db.scalars(select(DeletionBlob).where(DeletionBlob.request_id==row.id).with_for_update()))
    if blobs:
        await delete_verified([blob.url for blob in blobs])
        await db.execute(delete(DeletionBlob).where(DeletionBlob.request_id==row.id))
    row.status='COMPLETED';row.updated_at=row.completed_at=stamp();await db.commit();return output(row)

async def review(request_id,payload,admin,db):
    require_admin(admin)
    # Always lock the subject before its request: same order as submit/cancel/payment.
    snapshot=await db.get(AccountDeletion,request_id)
    if not snapshot:raise HTTPException(404,'Permintaan tidak ditemukan')
    subject=await db.scalar(select(User).where(User.id==snapshot.subject_id).with_for_update())
    row=await db.scalar(select(AccountDeletion).where(AccountDeletion.id==request_id).with_for_update().execution_options(populate_existing=True))
    if row.status=='COMPLETED':return output(row)
    if row.status=='CANCELLED':raise HTTPException(409,'Permintaan sudah dibatalkan')
    if payload.action=='REVIEW':
        if row.status=='PENDING':row.status='REVIEWING';row.reviewed_by=admin.id;row.updated_at=stamp()
        await db.commit();return output(row)
    if payload.confirmation!=str(row.id):raise HTTPException(422,'Konfirmasi nomor permintaan tidak cocok')
    if row.status=='CLEANUP':return await finish_blobs(row,db)
    if row.status!='REVIEWING':raise HTTPException(409,'Tinjau permintaan terlebih dahulu')
    if not subject:raise HTTPException(409,'Akun tidak tersedia')
    if is_admin(subject):raise HTTPException(409,'Cabut wewenang admin akun ini terlebih dahulu melalui dashboard admin')
    orders=list(await db.scalars(select(SubscriptionOrder).where(SubscriptionOrder.user_id==subject.id).with_for_update()))
    if any(o.state not in {'EXPIRED','CANCELLED','DENIED'} or o.renewal_state not in {'NONE','CANCELLED'} for o in orders):
        raise HTTPException(409,'Selesaikan pesanan dan pembatalan autodebit terlebih dahulu')
    if await db.scalar(select(SubscriptionPayment.id).join(SubscriptionOrder).where(SubscriptionOrder.user_id==subject.id).limit(1)):
        raise HTTPException(409,'Riwayat pembayaran perlu peninjauan retensi sebelum akun dapat dihapus')
    conditions=predicates(subject.id);photos=Base.metadata.tables['wishlist_photos']
    urls=list(await db.scalars(select(photos.c.blob_url).where(conditions['wishlist_photos'],photos.c.blob_url.is_not(None))))
    for url in set(urls):db.add(DeletionBlob(request_id=row.id,url=url))
    await db.flush()
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in conditions:await db.execute(delete(table).where(conditions[table.name]))
    # Keep only a request/subject UUID for the restore suppression manifest; no email/name.
    row.user_id=None;row.status='CLEANUP';row.updated_at=stamp();row.reviewed_by=admin.id
    await db.flush();await db.execute(delete(User).where(User.id==subject.id));await db.commit()
    return await finish_blobs(row,db)
