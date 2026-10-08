import os
import ssl
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = URL.create(
    "postgresql+asyncpg",
    username=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DATABASE_NAME", "finance_tracker"),
)
connect_args = {}
if os.getenv("DB_SSL", "false").strip().lower() in {"true", "1", "yes"}:
    connect_args["ssl"] = ssl.create_default_context()

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
