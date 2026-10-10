import json

import httpx
import pytest

from app.main import app
from app.routes import search_ai
from app.services import search_pipeline
from app.services.llm_service import LLMResponse
from app.services.prompt import PROMPT_VERSION

SQL = "SELECT u.id, u.nama FROM umkm.umkm AS u LIMIT 5"


@pytest.fixture
def client(monkeypatch):
    async def fake_generate(spec, system, user):
        if spec.key == "gpt-oss-120b":
            return LLMResponse(sql="DROP TABLE umkm.umkm", latency_ms=5)
        return LLMResponse(sql=SQL, json_strict=True, latency_ms=10, input_tokens=100)

    async def fake_execute(sql):
        return [{"id": 1, "nama": "Kopi"}], 3

    monkeypatch.setattr(search_pipeline, "generate_sql", fake_generate)
    monkeypatch.setattr(search_pipeline, "execute_ai_sql", fake_execute)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_search_ai_returns_per_model_results(client):
    async with client:
        resp = await client.post(
            "/api/v1/search/ai", json={"query": "kopi", "latitude": -6.3, "longitude": 106.8}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["prompt_strategy"] == "few_shot"
    assert body["results"]["gpt-oss-20b"]["status"] == "success"
    assert body["results"]["gpt-oss-20b"]["data"] == [{"id": 1, "nama": "Kopi"}]
    assert body["results"]["gpt-oss-20b"]["latency"]["db_ms"] == 3
    assert body["results"]["gpt-oss-120b"]["status"] == "blocked_by_sanitizer"
    assert body["results"]["gpt-oss-120b"]["data"] == []


async def test_single_model_and_strategy(client):
    async with client:
        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "kopi", "models": ["qwen3.8-27b"], "prompt_strategy": "zero_shot"},
        )
    assert list(resp.json()["results"]) == ["qwen3.8-27b"]


async def test_prompt_version_in_response_and_log(client, monkeypatch, tmp_path):
    log = tmp_path / "requests.jsonl"
    monkeypatch.setattr(search_ai.settings, "EXPERIMENT_LOG_PATH", str(log))
    async with client:
        resp = await client.post("/api/v1/search/ai", json={"query": "kopi"})
    assert resp.json()["prompt_version"] == PROMPT_VERSION
    assert json.loads(log.read_text())["prompt_version"] == PROMPT_VERSION


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "a" * 501},
        {"query": "kopi", "models": ["unknown"]},
        {"query": "kopi", "latitude": -6.3},
        {"query": "kopi", "prompt_strategy": "chain"},
    ],
)
async def test_invalid_requests(client, payload):
    async with client:
        resp = await client.post("/api/v1/search/ai", json=payload)
    assert resp.status_code == 422


async def test_api_key_required_when_configured(client, monkeypatch):
    monkeypatch.setattr(search_ai.settings, "API_KEY", "secret")
    async with client:
        assert (await client.post("/api/v1/search/ai", json={"query": "kopi"})).status_code == 401
        resp = await client.post(
            "/api/v1/search/ai", json={"query": "kopi"}, headers={"X-API-Key": "secret"}
        )
    assert resp.status_code == 200


async def test_rate_limit(client, monkeypatch):
    from app.core import rate_limit

    monkeypatch.setattr(rate_limit.settings, "RATE_LIMIT_PER_MINUTE", 2)
    rate_limit._hits.clear()
    async with client:
        codes = [
            (await client.post("/api/v1/search/ai", json={"query": "kopi"})).status_code
            for _ in range(3)
        ]
    assert codes == [200, 200, 429]
