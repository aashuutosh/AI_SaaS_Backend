import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import our application settings and models
from app.config.settings import get_settings
from app.models.base import Base

config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic to our SQLAlchemy models
target_metadata = Base.metadata

# Get the database URL from our Pydantic settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    """In this scenario we need to create an Engine
    and associate a connection with the context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"prepared_statement_cache_size": 0}  # Add this critical line
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

# We only support online migrations for this architecture
if context.is_offline_mode():
    print("Offline migrations are not supported. Please run online.")
else:
    run_migrations_online()