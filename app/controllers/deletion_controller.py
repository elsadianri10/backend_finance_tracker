from app.services import deletion_service as service
async def own(response,user,db):
    response.headers['Cache-Control']='no-store';return await service.own(user,db)
async def submit(payload,response,user,db):
    response.headers['Cache-Control']='no-store';return await service.submit(payload,user,db)
async def cancel(response,user,db):
    response.headers['Cache-Control']='no-store';return await service.cancel(user,db)
async def listing(response,user,db,offset,limit):
    response.headers['Cache-Control']='no-store';return await service.listing(user,db,offset,limit)
async def review(request_id,payload,response,user,db):
    response.headers['Cache-Control']='no-store';return await service.review(request_id,payload,user,db)
