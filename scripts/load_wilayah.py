#!/usr/bin/env python3
"""Load Indonesia administrative region data into PostgreSQL."""

import re
import os
import sys
import asyncio
from pathlib import Path

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SQL_FILES = [
    ("provinces", "scripts/provinces.sql"),
    ("regencies", "scripts/regencies.sql"),
    ("districts", "scripts/districts.sql"),
    ("villages", "scripts/villages.sql"),
]

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres@localhost:5432/ta_umkm",
)


def _extract_up_section(filepath: str) -> str:
    """Extract SQL between +migrate Up and +migrate Down markers."""
    content = Path(filepath).read_text(encoding="utf-8")
    match = re.search(
        r"-- \+migrate Up\s*\n(.*?)(?=-- \+migrate Down|\Z)",
        content,
        re.DOTALL,
    )
    return match.group(1).strip() if match else content.strip()


async def _load_tables(pool) -> None:
    """Load four region tables in FK order."""
    for label, filepath in SQL_FILES:
        sql = _extract_up_section(filepath)
        if not sql:
            print(f"  [{label}] No SQL found, skipping")
            continue
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        async with pool.acquire() as conn:
            for stmt in statements:
                if stmt and not stmt.startswith("--"):
                    try:
                        await conn.execute(stmt)
                    except Exception as e:
                        if "duplicate key" in str(e).lower():
                            print(f"  [{label}] Skipping duplicate: {e}")
                        else:
                            raise


async def _add_location_columns(pool) -> None:
    """Add geometry column and backfill from lat/lng for each table."""
    tables = ["provinces", "regencies", "districts", "villages"]
    async with pool.acquire() as conn:
        for table in tables:
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
                    f"ALTER TABLE public.{table} "
                    "ADD COLUMN location geometry(Point,4326)"
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


async def _verify(pool) -> None:
    """Print row counts and location coverage."""
    async with pool.acquire() as conn:
        for table in ["provinces", "regencies", "districts", "villages"]:
            total = await conn.fetchval(f"SELECT COUNT(*) FROM public.{table}")
            with_geom = await conn.fetchval(
                f"SELECT COUNT(*) FROM public.{table} WHERE location IS NOT NULL"
            )
            print(f"  {table}: {total} rows, {with_geom} with location")


async def main():
    pool = await asyncpg.create_pool(
        DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
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