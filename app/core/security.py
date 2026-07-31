import sqlglot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

ALLOWED_TABLES = {
    "umkm.umkm",
    "umkm.jenis_umkm",
    "public.districts",
    "public.provinces",
    "public.regencies",
    "public.villages",
}

MAX_QUERY_LENGTH = 500
MAX_RADIUS_METER = 5000
DEFAULT_LIMIT = 100

AI_EXECUTOR_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://postgres@",
    f"postgresql+asyncpg://readonly_ai_executor:{settings.AI_EXECUTOR_PASSWORD}@",
)

ai_executor_engine = create_async_engine(AI_EXECUTOR_DATABASE_URL)


def validate_user_query(query: str) -> bool:
    """Lapis 1: validate user natural language input."""
    if not query or not isinstance(query, str):
        return False
    if len(query) > MAX_QUERY_LENGTH:
        return False
    return True


def _extract_tables(expression: sqlglot.expressions.Expression) -> set[str]:
    tables = set()
    for table in expression.find_all(sqlglot.exp.Table):
        name = table.name
        db = table.db or "public"
        tables.add(f"{db}.{name}")
    return tables


def _ensure_limit(expression: sqlglot.expressions.Expression) -> sqlglot.expressions.Expression:
    if expression.args.get("limit") is None:
        expression = expression.limit(DEFAULT_LIMIT)
    return expression


def validate_sql(sql: str) -> tuple[bool, str, str | None]:
    """Lapis 2: structural validation with sqlglot.

    Returns (is_valid, status, sanitized_sql).
    """
    try:
        expressions = list(sqlglot.parse(sql, read="postgres"))
    except Exception:
        return False, "invalid_sql_syntax", None

    if len(expressions) != 1:
        return False, "blocked_by_sanitizer", None

    expression = expressions[0]

    if not isinstance(expression, sqlglot.exp.Select):
        return False, "blocked_by_sanitizer", None

    tables = _extract_tables(expression)
    if not tables or not tables.issubset(ALLOWED_TABLES):
        return False, "blocked_by_sanitizer", None

    expression = _ensure_limit(expression)

    for param in expression.find_all(sqlglot.exp.Literal):
        if not param.is_number:
            continue
        try:
            value = float(param.this)
        except (TypeError, ValueError):
            continue
        if value > MAX_RADIUS_METER and (
            param.parent and "radius" in str(param.parent).lower()
        ):
            return False, "blocked_by_sanitizer", None

    return True, "success", expression.sql(dialect="postgres")


async def execute_ai_sql(sql: str) -> list[dict]:
    """Execute validated SQL via read-only role with statement timeout."""
    async with ai_executor_engine.connect() as conn:
        await conn.execute(
            text(f"SET statement_timeout = {settings.DB_STATEMENT_TIMEOUT_MS}")
        )
        result = await conn.execute(text(sql))
    return [dict(r) for r in result.mappings()]
