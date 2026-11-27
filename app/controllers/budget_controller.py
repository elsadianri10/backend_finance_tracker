from app.controllers.routine_controller import no_store
from app.services import budget_service as service


async def listing(response, user, db):
    no_store(response)
    return await service.list_budgets(user.id, db)


async def save(payload, response, user, db, budget_id=None):
    no_store(response)
    return await service.save(payload, user.id, db, budget_id)


async def delete(budget_id, version, response, user, db):
    no_store(response)
    await service.delete(budget_id, user.id, version, db)
