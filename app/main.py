from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.search_ai import router as search_ai_router
from app.routes.search_manual import router as search_manual_router

app = FastAPI(title="Text-to-Spatial-SQL UMKM", version="0.1.0")

app.include_router(health_router)
app.include_router(search_manual_router)
app.include_router(search_ai_router)
