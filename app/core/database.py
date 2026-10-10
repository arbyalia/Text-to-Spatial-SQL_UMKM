from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings

# Owner role (DATABASE_URL). Only scripts/ use it; the API never needs it.
engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Read-only role (AI_EXECUTOR_DATABASE_URL). Every API query goes through this engine.
readonly_engine: AsyncEngine = create_async_engine(
    settings.AI_EXECUTOR_DATABASE_URL, pool_pre_ping=True
)
