from pydantic import BaseModel, Field


class SearchManualRequest(BaseModel):
    latitude: float
    longitude: float
    radius_meter: int = Field(gt=0, le=5000)
    jenis_umkm_id: int | None = None


class UkmResult(BaseModel):
    id: int
    nama: str
    alamat: str | None
    rating: float | None
    jml_ulasan: int
    latitude: float | None
    longitude: float | None
    jarak_meter: float


class SearchManualResponse(BaseModel):
    query_used: str
    count: int
    results: list[UkmResult]