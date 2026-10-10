import time
from datetime import date, datetime
from decimal import Decimal

from app.core.security import execute_ai_sql, validate_sql
from app.schemas.search import Latency, ModelResult
from app.services.llm_service import generate_sql
from app.services.model_registry import ModelSpec


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    return value


async def run_model(spec: ModelSpec, system: str, user: str) -> ModelResult:
    """LLM -> sanitizer -> read-only execution for one model."""
    start = time.perf_counter()
    llm = await generate_sql(spec, system, user)

    def result(status, sql=None, db_ms=None, error=None, data=()):
        rows = [{k: _json_safe(v) for k, v in row.items()} for row in data]
        return ModelResult(
            model=spec.key,
            model_id=spec.model_id,
            status=status,
            sql=sql,
            raw_sql=llm.sql,
            json_strict=llm.json_strict,
            latency=Latency(
                llm_ms=llm.latency_ms,
                db_ms=db_ms,
                total_ms=int((time.perf_counter() - start) * 1000),
            ),
            input_tokens=llm.input_tokens,
            output_tokens=llm.output_tokens,
            error_message=error,
            count=len(rows),
            data=rows,
        )

    if llm.error:
        return result("invalid_json" if llm.error == "invalid_json" else "error", error=llm.error)

    check = validate_sql(llm.sql)
    if not check.valid:
        return result(check.status, error=check.reason)

    try:
        rows, db_ms = await execute_ai_sql(check.sql)
    except Exception as e:
        message = str(getattr(e, "orig", e)).splitlines()[0][:300]
        return result("db_execution_error", sql=check.sql, error=message)

    return result("success", sql=check.sql, db_ms=db_ms, data=rows)
