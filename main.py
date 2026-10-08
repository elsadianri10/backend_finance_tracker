import json
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv

load_dotenv(".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.config.db_config import engine
from app.routes import auth_router, version_router, billing_router
from app.routes.debt_route import router as debt_router
from app.routes.bank_account_route import router as bank_account_router
from app.routes.savings_route import router as savings_router


def parse_origins(raw: str) -> list[str]:
    if raw.strip().startswith("["):
        origins = json.loads(raw)
        if not isinstance(origins, list) or not all(isinstance(x, str) for x in origins):
            raise ValueError("ORIGINS must be a JSON array of strings")
        return origins
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Finance Tracker API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc: RequestValidationError):
    # Pydantic's default errors echo the input, including card numbers or tokens.
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]},
        headers={"Cache-Control": "no-store"},
    )


app.include_router(version_router)
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(billing_router)
app.include_router(debt_router)
app.include_router(bank_account_router)
app.include_router(savings_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(os.getenv("ORIGINS", "http://localhost:5173")),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

if __name__ == "__main__":
    uvicorn.run("main:app", host=os.getenv("HOST_SERVER", "127.0.0.1"), port=int(os.getenv("PORT_SERVER", "8000")))
