from fastapi.responses import JSONResponse
from app.config import VERSION

async def get_version():
    return JSONResponse(
        status_code=200,
        content={
            "Status": "Success",
            "Version": VERSION,
        }
    )
