from dataclasses import dataclass, field

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine


@dataclass
class Catalog:
    categories: dict[int, str] = field(default_factory=dict)
    districts: list[str] = field(default_factory=list)


catalog = Catalog()


async def load_catalog() -> Catalog:
    """Load UMKM categories and study-area district names used to build the prompt."""
    async with engine.connect() as conn:
        categories = (
            await conn.execute(text("SELECT id, nama FROM umkm.jenis_umkm ORDER BY id"))
        ).all()
        districts = (
            (
                await conn.execute(
                    text("SELECT name FROM public.districts WHERE regency_id = :rid ORDER BY name"),
                    {"rid": settings.STUDY_AREA_REGENCY_ID},
                )
            )
            .scalars()
            .all()
        )
    catalog.categories = {row.id: row.nama for row in categories}
    catalog.districts = list(districts)
    return catalog
