import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.security import verify_executor_role
from app.routes.health import router as health_router
from app.routes.search_ai import router as search_ai_router
from app.routes.search_manual import router as search_manual_router
from app.services.catalog import load_catalog

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    role = await verify_executor_role()
    catalog = await load_catalog()
    logger.info(
        "AI executor role: %s; %d categories, %d districts loaded",
        role,
        len(catalog.categories),
        len(catalog.districts),
    )
    yield


app = FastAPI(title="Text-to-Spatial-SQL UMKM", version="0.2.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(search_manual_router)
app.include_router(search_ai_router)
