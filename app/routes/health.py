import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import readonly_engine

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
async def health() -> dict[str, str] | JSONResponse:
    try:
        async with readonly_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.warning("health check failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "detail": "database connection failed",
            },
        )
