from app.services import admin_role_service as service
async def change(target_id,payload,response,user,db):
    response.headers['Cache-Control']='no-store';return await service.change(target_id,payload,user,db)
async def history(target_id,response,user,db):
    response.headers['Cache-Control']='no-store';return await service.history(target_id,user,db)
