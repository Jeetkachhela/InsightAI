import os
import sys
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context

# Add backend directory to sys.path to resolve app imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.database import Base, engine
import app.models.models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set models metadata
target_metadata = Base.metadata

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name.startswith("olist_"):
        return False
    return True

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    # Ensure correct dialect for asyncpg if postgres
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations using the pre-configured async engine."""
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Run in the current async loop or create a new one
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If already in an event loop, run as a task
        loop.create_task(run_async_migrations())
    else:
        asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
