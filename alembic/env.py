import asyncio

# 1. Import your application's config and models
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Ensure the 'src' directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import config

# Import all models to ensure they are registered with Base.metadata
from src.db.base import Base

# 2. Alembic Config object
alembic_config = context.config

# 3. Setup logging
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# 4. Set target_metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.async_db_url

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Recommended for SQLite/flexible migrations
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """

    # We use the app's engine configuration logic but through alembic's config if preferred,
    # or just use our already existing engine from src.db.client.
    # However, to be strictly "Alembic-way", we can use async_engine_from_config

    # Get the URL from our centralized config
    url = config.async_db_url

    configuration = alembic_config.get_section(alembic_config.config_ini_section, {})
    if url:
        configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
