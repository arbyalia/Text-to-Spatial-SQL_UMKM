from typing import Literal

from pydantic import BaseModel, Field

from app.core.security import MAX_QUERY_LENGTH


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


class SearchAiRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)


class ModelResult(BaseModel):
    status: Literal[
        "success",
        "invalid_json",
        "invalid_sql_syntax",
        "blocked_by_sanitizer",
        "db_execution_error",
        "error",
    ]
    sql: str | None
    latency_ms: int
    error_message: str | None
    data: list[dict]


class SearchAiResponse(BaseModel):
    query: str
    results: dict[Literal["gemini", "gpt", "deepseek"], ModelResult]
