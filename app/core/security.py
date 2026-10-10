import time
from dataclasses import dataclass

import sqlglot
from sqlalchemy import text
from sqlglot import exp

from app.core.config import settings
from app.core.database import readonly_engine

ALLOWED_TABLES = {
    "umkm.umkm",
    "umkm.jenis_umkm",
    "public.provinces",
    "public.regencies",
    "public.districts",
    "public.villages",
}

ALLOWED_UNTYPED_FUNCTIONS = {
    "split_part",
    "string_to_array",
    "regexp_split_to_table",
    "initcap",
    "unnest",
    "to_char",
    "date_part",
    "json_agg",
    "jsonb_agg",
    "json_build_object",
    "jsonb_build_object",
    "geography",
    "geometry",
}

MAX_QUERY_LENGTH = 500
MAX_RADIUS_METER = 5000
DEFAULT_LIMIT = 100
MAX_LIMIT = 500


@dataclass
class SqlValidation:
    valid: bool
    status: str
    sql: str | None
    reason: str | None = None


def validate_user_query(query: str) -> bool:
    """Lapis 1: validate user natural language input."""
    return isinstance(query, str) and 0 < len(query.strip()) <= MAX_QUERY_LENGTH


def _const_value(node: exp.Expression) -> float | None:
    if isinstance(node, exp.Literal) and not node.is_string:
        return float(node.this)
    if isinstance(node, (exp.Paren, exp.Cast)):
        return _const_value(node.this)
    if isinstance(node, exp.Neg):
        value = _const_value(node.this)
        return None if value is None else -value
    if isinstance(node, (exp.Mul, exp.Add, exp.Sub, exp.Div)):
        left, right = _const_value(node.left), _const_value(node.right)
        if left is None or right is None:
            return None
        if isinstance(node, exp.Mul):
            return left * right
        if isinstance(node, exp.Add):
            return left + right
        if isinstance(node, exp.Sub):
            return left - right
        return left / right if right else None
    return None


def _function_name(func: exp.Func) -> str:
    if isinstance(func, exp.Anonymous):
        return str(func.this).lower()
    return func.sql_name().lower()


def _function_args(func: exp.Func) -> list[exp.Expression]:
    if isinstance(func, exp.Anonymous):
        return list(func.expressions)
    return [v for v in func.args.values() if isinstance(v, exp.Expression)]


def _check_functions(expression: exp.Expression) -> str | None:
    for func in expression.find_all(exp.Func):
        if not isinstance(func, exp.Anonymous):
            continue
        name = _function_name(func)
        if not (name.startswith("st_") or name in ALLOWED_UNTYPED_FUNCTIONS):
            return f"function not allowed: {name}"
    return None


def _is_geography(node: exp.Expression) -> bool:
    while isinstance(node, exp.Paren):
        node = node.this
    if isinstance(node, exp.Cast):
        return node.to.is_type(exp.DataType.Type.GEOGRAPHY)
    return isinstance(node, exp.Func) and _function_name(node) == "geography"


def _check_radius_value(node: exp.Expression, func: str) -> str | None:
    radius = _const_value(node)
    if radius is None:
        return f"{func} radius must be a numeric constant"
    if radius > MAX_RADIUS_METER:
        return f"radius exceeds {MAX_RADIUS_METER} m"
    return None


def _check_dwithin(expression: exp.Expression) -> str | None:
    for func in expression.find_all(exp.Func):
        if _function_name(func) != "st_dwithin":
            continue
        args = _function_args(func)
        if len(args) < 3:
            return "ST_DWithin requires a radius"
        if not (_is_geography(args[0]) and _is_geography(args[1])):
            return "ST_DWithin must use geography"
        reason = _check_radius_value(args[2], "ST_DWithin")
        if reason:
            return reason
    return None


def _distance_bound(comparison: exp.Expression) -> tuple[exp.Func, exp.Expression] | None:
    """Return (ST_Distance call, upper bound) when the comparison caps a distance from above."""
    if isinstance(comparison, exp.Between):
        candidates = [(comparison.this, comparison.args.get("high"))]
    elif isinstance(comparison, (exp.LT, exp.LTE)):
        candidates = [(comparison.this, comparison.expression)]
    elif isinstance(comparison, (exp.GT, exp.GTE)):
        candidates = [(comparison.expression, comparison.this)]
    else:
        return None
    for side, bound in candidates:
        while isinstance(side, (exp.Paren, exp.Cast)):
            side = side.this
        if isinstance(side, exp.Func) and _function_name(side) == "st_distance":
            return side, bound
    return None


def _check_distance_filters(expression: exp.Expression) -> str | None:
    clauses = [*expression.find_all(exp.Where, exp.Having)]
    clauses += [j.args["on"] for j in expression.find_all(exp.Join) if j.args.get("on")]
    for clause in clauses:
        for comparison in clause.find_all(exp.Between, exp.LT, exp.LTE, exp.GT, exp.GTE):
            found = _distance_bound(comparison)
            if found is None:
                continue
            func, bound = found
            args = _function_args(func)
            if len(args) < 2 or not (_is_geography(args[0]) and _is_geography(args[1])):
                return "ST_Distance must use geography"
            reason = _check_radius_value(bound, "ST_Distance")
            if reason:
                return reason
    return None


def _check_tables(expression: exp.Expression) -> str | None:
    cte_names = {cte.alias_or_name.lower() for cte in expression.find_all(exp.CTE)}
    tables = set()
    for table in expression.find_all(exp.Table):
        if not table.db and table.name.lower() in cte_names:
            continue
        tables.add(f"{(table.db or 'public').lower()}.{table.name.lower()}")
    if not tables:
        return "no table referenced"
    outside = tables - ALLOWED_TABLES
    if outside:
        return f"table not allowed: {', '.join(sorted(outside))}"
    return None


def _apply_limit(expression: exp.Query) -> exp.Query:
    limit = expression.args.get("limit")
    if limit is None:
        return expression.limit(DEFAULT_LIMIT)
    value = _const_value(limit.expression) if limit.expression else None
    if value is None or value > MAX_LIMIT:
        return expression.limit(MAX_LIMIT)
    return expression


def _select_branches(expression: exp.Expression) -> list[exp.Expression]:
    while isinstance(expression, (exp.Subquery, exp.Paren)):
        expression = expression.this
    if isinstance(expression, exp.SetOperation):
        return _select_branches(expression.this) + _select_branches(expression.expression)
    return [expression]


def validate_sql(sql: str | None) -> SqlValidation:
    """Lapis 2: structural validation of LLM-generated SQL with sqlglot."""
    if not sql or not sql.strip():
        return SqlValidation(False, "invalid_sql_syntax", None, "empty sql")
    try:
        expressions = [e for e in sqlglot.parse(sql, read="postgres") if e is not None]
    except sqlglot.errors.SqlglotError as e:
        return SqlValidation(False, "invalid_sql_syntax", None, str(e).splitlines()[0])

    if len(expressions) != 1:
        return SqlValidation(False, "blocked_by_sanitizer", None, "multiple statements")

    expression = expressions[0]
    branches = _select_branches(expression)
    if not all(isinstance(b, exp.Select) for b in branches):
        return SqlValidation(False, "blocked_by_sanitizer", None, "only SELECT is allowed")
    if any(b.args.get("into") is not None or b.args.get("locks") for b in branches):
        return SqlValidation(
            False, "blocked_by_sanitizer", None, "SELECT INTO / locking not allowed"
        )

    for check in (_check_tables, _check_functions, _check_dwithin, _check_distance_filters):
        reason = check(expression)
        if reason:
            return SqlValidation(False, "blocked_by_sanitizer", None, reason)

    return SqlValidation(True, "success", _apply_limit(expression).sql(dialect="postgres"))


async def verify_executor_role() -> str:
    """Lapis 3: refuse to run AI SQL through a role that can write or is superuser."""
    async with readonly_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT current_user AS name, rolsuper, rolcreaterole, rolcreatedb "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one()
    if row.rolsuper or row.rolcreaterole or row.rolcreatedb:
        raise RuntimeError(f"AI executor role '{row.name}' is privileged; use a read-only role")
    return row.name


async def execute_ai_sql(sql: str) -> tuple[list[dict], int]:
    """Lapis 3 & 4: run validated SQL in a read-only transaction with a statement timeout."""
    start = time.perf_counter()
    async with readonly_engine.connect() as conn:
        await conn.execute(text("SET TRANSACTION READ ONLY"))
        await conn.execute(
            text(f"SET LOCAL statement_timeout = {int(settings.DB_STATEMENT_TIMEOUT_MS)}")
        )
        rows = [dict(r) for r in (await conn.execute(text(sql))).mappings()]
        await conn.rollback()
    return rows, int((time.perf_counter() - start) * 1000)
