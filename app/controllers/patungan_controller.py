from app.controllers.routine_controller import no_store
from app.services.access_service import require_pro


async def execute(action, response, user, db, *args):
    no_store(response)
    await require_pro(user.id, db)
    return await action(*args, user.id, db)
