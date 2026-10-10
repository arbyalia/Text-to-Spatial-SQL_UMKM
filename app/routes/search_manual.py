from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.auth import require_api_key
from app.core.database import readonly_engine
from app.schemas.search import SearchManualRequest, SearchManualResponse, UmkmResult

router = APIRouter(prefix="/api/v1", tags=["search"], dependencies=[Depends(require_api_key)])


@router.post("/search/manual", response_model=SearchManualResponse)
async def search_manual(req: SearchManualRequest):
    params = {
        "lat": req.latitude,
        "lng": req.longitude,
        "radius": req.radius_meter,
    }
    jenis_filter = ""
    if req.jenis_umkm_id is not None:
        jenis_filter = "AND u.jenis_umkm_id = :jenis_umkm_id"
        params["jenis_umkm_id"] = req.jenis_umkm_id

    sql = f"""
    SELECT
        u.id, u.nama, u.alamat, u.rating, u.jml_ulasan,
        u.latitude, u.longitude,
        ROUND(
            ST_Distance(
                u.location::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            )::numeric, 2
        ) AS jarak_meter
    FROM umkm.umkm AS u
    WHERE
        u.location IS NOT NULL
        {jenis_filter}
        AND ST_DWithin(
            u.location::geography,
            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
            :radius
        )
    ORDER BY jarak_meter ASC
    """

    async with readonly_engine.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()

    results = [UmkmResult(**dict(r)) for r in rows]
    return SearchManualResponse(query_used=sql.strip(), count=len(results), results=results)
