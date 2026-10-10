from fastapi import APIRouter
from app.controllers import version_controller as controller

router = APIRouter()

@router.get("/version")
async def versi():
    return await controller.get_version()
