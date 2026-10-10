from typing import Literal

from pydantic import BaseModel, Field

from app.core.security import MAX_QUERY_LENGTH, MAX_RADIUS_METER

Status = Literal[
    "success",
    "invalid_json",
    "invalid_sql_syntax",
    "blocked_by_sanitizer",
    "db_execution_error",
    "error",
]


class SearchManualRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_meter: int = Field(gt=0, le=MAX_RADIUS_METER)
    jenis_umkm_id: int | None = None


class UmkmResult(BaseModel):
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
    results: list[UmkmResult]


class SearchAiRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    models: list[str] | None = Field(
        default=None, description="Kunci model; kosong berarti semua model yang aktif"
    )
    prompt_strategy: Literal["zero_shot", "few_shot"] | None = None


class Latency(BaseModel):
    llm_ms: int
    db_ms: int | None
    total_ms: int


class ModelResult(BaseModel):
    model: str
    model_id: str
    status: Status
    sql: str | None
    raw_sql: str | None
    json_strict: bool
    latency: Latency
    input_tokens: int | None
    output_tokens: int | None
    error_message: str | None
    count: int
    data: list[dict]


class SearchAiResponse(BaseModel):
    request_id: str
    query: str
    prompt_strategy: str
    results: dict[str, ModelResult]


class ModelInfo(BaseModel):
    key: str
    provider: str
    model_id: str
    params: dict
    note: str
    available: bool
