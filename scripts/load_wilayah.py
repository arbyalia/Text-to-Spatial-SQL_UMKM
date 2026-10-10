"""Load Indonesia administrative region data into PostgreSQL.

Usage (from the repository root): python -m scripts.load_wilayah
"""

import asyncio
import re
from pathlib import Path

import asyncpg

from app.core.config import settings

SQL_DIR = Path(__file__).parent
# FK order: each table references the previous one.
TABLES = ["provinces", "regencies", "districts", "villages"]


def _extract_up_section(path: Path) -> str:
    """Extract SQL between +migrate Up and +migrate Down markers."""
    content = path.read_text(encoding="utf-8")
    match = re.search(
        r"-- \+migrate Up\s*\n(.*?)(?=-- \+migrate Down|\Z)",
        content,
        re.DOTALL,
    )
    return match.group(1).strip() if match else content.strip()


async def _load_tables(pool: asyncpg.Pool) -> None:
    for label in TABLES:
        sql = _extract_up_section(SQL_DIR / f"{label}.sql")
        if not sql:
            print(f"  [{label}] No SQL found, skipping")
            continue
        sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        statements = [s.strip() for s in sql.split(";\n") if s.strip()]
        async with pool.acquire() as conn:
            for stmt in statements:
                try:
                    await conn.execute(stmt)
                except asyncpg.UniqueViolationError as e:
                    print(f"  [{label}] Skipping duplicate: {e}")


async def _add_location_columns(pool: asyncpg.Pool) -> None:
    """Add geometry column and backfill from lat/lng for each table."""
    async with pool.acquire() as conn:
        for table in TABLES:
            col_exists = await conn.fetchval(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                  AND column_name = 'location'
                """,
                table,
            )
            if not col_exists:
                await conn.execute(
                    f"ALTER TABLE public.{table} ADD COLUMN location geometry(Point,4326)"
                )

            result = await conn.execute(
                f"""
                UPDATE public.{table}
                SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
                WHERE latitude != 0 AND longitude != 0
                """
            )
            rows = result.split()[-1] if result else "0"
            print(f"  [{table}] Backfilled location: {rows} rows")


async def _verify(pool: asyncpg.Pool) -> None:
    """Print row counts and location coverage."""
    async with pool.acquire() as conn:
        for table in TABLES:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM public.{table}")
            with_geom = await conn.fetchval(
                f"SELECT COUNT(*) FROM public.{table} WHERE location IS NOT NULL"
            )
            print(f"  {table}: {total} rows, {with_geom} with location")


async def main() -> None:
    pool = await asyncpg.create_pool(
        settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
        min_size=1,
        max_size=2,
    )
    try:
        await _load_tables(pool)
        await _add_location_columns(pool)
        await _verify(pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
