from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.controllers import get_version

router = APIRouter()

@router.get("/version")
async def versi():
    result = await get_version()
    if result:
        return result
    return JSONResponse(
        status_code=401,
        content={"Status": "Error", "Message": "Unauthorized Access"}
    )
