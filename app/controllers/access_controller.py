from app.services import access_service as service


async def mine(response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    return await service.mine(user, db)


async def users(response, user, db, search, offset, limit):
    response.headers['Cache-Control'] = 'no-store'
    return await service.users(user, db, search, offset, limit)


async def change(target_id, payload, response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    return await service.change(target_id, payload, user, db)


async def history(target_id, response, user, db):
    response.headers['Cache-Control'] = 'no-store'
    return await service.history(target_id, user, db)


async def usage(response, user, db):
    from app.services.plan_service import usage as account_usage
    response.headers['Cache-Control'] = 'no-store'
    return await account_usage(user, db)


def plans(response):
    from app.services.plan_service import catalog
    response.headers['Cache-Control'] = 'no-store'
    return catalog()
