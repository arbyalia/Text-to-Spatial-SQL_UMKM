from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy.engine import make_url

from app.core import database, security
from app.core.config import settings
from app.main import app
from app.routes import health, search_manual
from app.services import catalog

ROW = {
    "id": 1,
    "nama": "Kopi",
    "alamat": None,
    "rating": 4.5,
    "jml_ulasan": 10,
    "latitude": -6.3,
    "longitude": 106.8,
    "jarak_meter": 12.5,
}


class FakeResult:
    def mappings(self):
        return self

    def all(self):
        return [ROW]


class FakeEngine:
    def __init__(self):
        self.statements = []

    @asynccontextmanager
    async def connect(self):
        yield self

    async def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return FakeResult()


class ForbiddenEngine:
    def connect(self):
        raise AssertionError("API must not use the owner engine")


@pytest.fixture
def readonly(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr(database, "engine", ForbiddenEngine())
    for module in (health, search_manual):
        monkeypatch.setattr(module, "readonly_engine", fake)
    return fake


@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def test_api_modules_import_only_readonly_engine():
    for module in (health, search_manual, catalog, security):
        assert module.readonly_engine is database.readonly_engine
        assert not hasattr(module, "engine")


def test_readonly_engine_uses_executor_url():
    assert database.readonly_engine.url == make_url(settings.AI_EXECUTOR_DATABASE_URL)


async def test_health_uses_readonly_engine(client, readonly):
    async with client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert readonly.statements == ["SELECT 1"]


async def test_search_manual_uses_readonly_engine(client, readonly):
    async with client:
        resp = await client.post(
            "/api/v1/search/manual",
            json={"latitude": -6.3, "longitude": 106.8, "radius_meter": 500},
        )
    assert resp.status_code == 200
    assert resp.json()["results"] == [ROW]
    assert len(readonly.statements) == 1 and "ST_DWithin" in readonly.statements[0]
