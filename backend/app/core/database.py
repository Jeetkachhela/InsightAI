import re
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Automatically convert postgresql:// to postgresql+asyncpg:// if not already present
db_url = settings.DATABASE_URL
connect_args = {"statement_cache_size": 0}

if "postgresql" in db_url or "postgres" in db_url:
    if "sslmode" in db_url:
        # Strip query parameters for asyncpg compatibility and use connect_args
        db_url = db_url.split("?")[0]
        connect_args["ssl"] = "require"
        
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Configure PG pool settings in production (DB-003)
is_postgres = "postgresql" in db_url or "postgres" in db_url
pool_args = {}
if is_postgres:
    pool_args.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800
    })

# Configure async engine
engine = create_async_engine(
    db_url,
    pool_pre_ping=True,
    future=True,
    connect_args=connect_args,
    **pool_args
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession
)

Base = declarative_base()

# Dependency to get db session in FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
