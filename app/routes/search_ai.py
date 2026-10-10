import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_api_key
from app.core.config import settings
from app.core.experiment_log import append_log
from app.schemas.search import ModelInfo, SearchAiRequest, SearchAiResponse
from app.services.catalog import catalog
from app.services.model_registry import MODELS, enabled_models, has_api_key
from app.services.prompt import build_system_prompt, build_user_message
from app.services.search_pipeline import run_model

router = APIRouter(prefix="/api/v1", tags=["search"], dependencies=[Depends(require_api_key)])


@router.get("/models", response_model=list[ModelInfo])
async def list_models():
    return [
        ModelInfo(
            key=spec.key,
            provider=spec.provider,
            model_id=spec.model_id,
            params=spec.params,
            note=spec.note,
            available=has_api_key(spec),
        )
        for spec in enabled_models()
    ]


@router.post("/search/ai", response_model=SearchAiResponse)
async def search_ai(req: SearchAiRequest):
    if req.models:
        unknown = [m for m in req.models if m not in MODELS]
        if unknown:
            raise HTTPException(status_code=422, detail=f"unknown models: {', '.join(unknown)}")
        specs = [MODELS[m] for m in req.models]
    else:
        specs = enabled_models()
    if (req.latitude is None) != (req.longitude is None):
        raise HTTPException(status_code=422, detail="latitude and longitude must be sent together")

    strategy = req.prompt_strategy or settings.DEFAULT_PROMPT_STRATEGY
    system = build_system_prompt(catalog, strategy)
    user = build_user_message(req.query, req.latitude, req.longitude)

    results = await asyncio.gather(*(run_model(spec, system, user) for spec in specs))
    response = SearchAiResponse(
        request_id=uuid.uuid4().hex,
        query=req.query,
        prompt_strategy=strategy,
        results={r.model: r for r in results},
    )

    await append_log(
        {
            "request_id": response.request_id,
            "query": req.query,
            "latitude": req.latitude,
            "longitude": req.longitude,
            "prompt_strategy": strategy,
            "results": [r.model_dump(exclude={"data"}) for r in results],
        }
    )
    return response
