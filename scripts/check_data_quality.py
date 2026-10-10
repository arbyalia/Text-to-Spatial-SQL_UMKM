#!/usr/bin/env python3
"""Report data-quality problems in umkm.umkm before running experiments.

Checks: missing coordinates, location/lat-lon mismatch, points outside the study area,
district_id that disagrees with the spatially nearest district centroid or with the
kecamatan written in the address, categories without rows, duplicate names at the same spot.
"""

import asyncio
import re

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine

CHECKS = {
    "missing_coordinates": """
        SELECT id, nama FROM umkm.umkm
        WHERE location IS NULL OR latitude IS NULL OR longitude IS NULL
    """,
    "location_differs_from_lat_lon": """
        SELECT id, nama FROM umkm.umkm
        WHERE location IS NOT NULL
          AND ST_Distance(location::geography,
                          ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) > 10
    """,
    "district_outside_study_area": """
        SELECT u.id, u.nama, u.district_id FROM umkm.umkm u
        LEFT JOIN public.districts d ON d.id = u.district_id
        WHERE d.regency_id IS DISTINCT FROM :rid
    """,
    "far_from_study_area": """
        SELECT u.id, u.nama,
               ROUND(MIN(ST_Distance(u.location::geography, d.location::geography))) AS meter
        FROM umkm.umkm u CROSS JOIN public.districts d
        WHERE d.regency_id = :rid AND u.location IS NOT NULL
        GROUP BY u.id, u.nama
        HAVING MIN(ST_Distance(u.location::geography, d.location::geography)) > 8000
    """,
    "duplicate_name_and_location": """
        SELECT MIN(id) AS id, nama, COUNT(*) AS n FROM umkm.umkm
        GROUP BY nama, ROUND(latitude::numeric, 4), ROUND(longitude::numeric, 4) HAVING COUNT(*) > 1
    """,
    "category_without_rows": """
        SELECT j.id, j.nama FROM umkm.jenis_umkm j
        LEFT JOIN umkm.umkm u ON u.jenis_umkm_id = j.id WHERE u.id IS NULL
    """,
}

DISTRICT_SQL = """
    SELECT u.id, u.alamat, d.name AS coded, near.name AS nearest
    FROM umkm.umkm u
    JOIN public.districts d ON d.id = u.district_id
    CROSS JOIN LATERAL (
        SELECT name FROM public.districts
        WHERE regency_id = :rid AND location IS NOT NULL
        ORDER BY location <-> u.location LIMIT 1
    ) near
    WHERE u.location IS NOT NULL
"""

KECAMATAN = re.compile(r"(?:Kecamatan|Kec\.)\s+([A-Za-z ]+?)\s*(?:\.|,|$)", re.IGNORECASE)


def _norm(name: str) -> str:
    return name.upper().replace(" ", "")


async def main() -> None:
    params = {"rid": settings.STUDY_AREA_REGENCY_ID}
    async with engine.connect() as conn:
        total = (await conn.execute(text("SELECT COUNT(*) FROM umkm.umkm"))).scalar()
        per_category = (
            await conn.execute(
                text(
                    "SELECT j.nama, COUNT(u.id) FROM umkm.jenis_umkm j "
                    "LEFT JOIN umkm.umkm u ON u.jenis_umkm_id = j.id "
                    "GROUP BY j.nama ORDER BY 2 DESC"
                )
            )
        ).all()
        print(f"Total UMKM: {total}")
        for name, count in per_category:
            print(f"  {name}: {count}")

        for label, sql in CHECKS.items():
            rows = (await conn.execute(text(sql), params)).all()
            print(f"\n[{'OK' if not rows else 'CHECK'}] {label}: {len(rows)}")
            for row in rows[:5]:
                print("   ", tuple(row))

        rows = (await conn.execute(text(DISTRICT_SQL), params)).all()

    address_mismatch = []
    nearest_mismatch = 0
    for row in rows:
        if _norm(row.coded) != _norm(row.nearest):
            nearest_mismatch += 1
        match = KECAMATAN.search(row.alamat or "")
        if match and not _norm(match.group(1)).startswith(_norm(row.coded)):
            address_mismatch.append((row.id, row.coded, match.group(1).strip()))

    print(
        f"\n[{'OK' if not address_mismatch else 'CHECK'}] "
        f"district_id differs from kecamatan in address: {len(address_mismatch)}"
    )
    pairs: dict[tuple[str, str], int] = {}
    for _, coded, written in address_mismatch:
        key = (coded, written.upper())
        pairs[key] = pairs.get(key, 0) + 1
    for (coded, written), n in sorted(pairs.items(), key=lambda kv: -kv[1]):
        print(f"    coded {coded!r} but address says {written!r}: {n}")
    print(
        f"\n[INFO] district_id differs from nearest district centroid: "
        f"{nearest_mismatch} of {len(rows)} "
        "(centroids are approximate; read together with the address check)"
    )


if __name__ == "__main__":
    asyncio.run(main())
