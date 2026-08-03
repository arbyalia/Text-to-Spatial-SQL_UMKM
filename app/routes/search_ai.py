from decimal import Decimal

from fastapi import APIRouter

from app.core.security import execute_ai_sql, validate_sql, validate_user_query
from app.schemas.search import ModelResult, SearchAiRequest, SearchAiResponse
from app.services.llm_service import LLMResponse, generate_sql_parallel

router = APIRouter(tags=["search"])


def _normalize(row: dict) -> dict:
    return {
        k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()
    }


async def _build_result(response: LLMResponse, latency_ms: int) -> ModelResult:
    if response.error:
        if response.error == "invalid_json":
            return ModelResult(
                status="invalid_json",
                sql=None,
                latency_ms=latency_ms,
                error_message=response.error,
                data=[],
            )
        return ModelResult(
            status="error",
            sql=None,
            latency_ms=latency_ms,
            error_message=response.error,
            data=[],
        )

    valid, status, sanitized_sql = validate_sql(response.sql)
    if not valid:
        return ModelResult(
            status=status,
            sql=response.sql,
            latency_ms=latency_ms,
            error_message=status,
            data=[],
        )

    try:
        rows = [_normalize(r) for r in await execute_ai_sql(sanitized_sql)]
    except Exception as e:
        return ModelResult(
            status="db_execution_error",
            sql=sanitized_sql,
            latency_ms=latency_ms,
            error_message=str(e.__class__.__name__),
            data=[],
        )

    return ModelResult(
        status="success",
        sql=sanitized_sql,
        latency_ms=latency_ms,
        error_message=None,
        data=rows,
    )


@router.post("/search/ai", response_model=SearchAiResponse)
async def search_ai(req: SearchAiRequest):
    if not validate_user_query(req.query):
        return SearchAiResponse(
            query=req.query,
            results={},
        )

    llm_results = await generate_sql_parallel(req.query)
    results = {
        name: await _build_result(resp, latency)
        for name, (resp, latency) in llm_results.items()
    }

    return SearchAiResponse(query=req.query, results=results)