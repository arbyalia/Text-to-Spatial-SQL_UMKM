"""Runs against a database built by db/setup.sh (see .github/workflows/test.yml)."""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.skipif(
    "AI_EXECUTOR_PASSWORD" not in os.environ, reason="needs a database built by db/setup.sh"
)

from app.core.security import execute_ai_sql, validate_sql, verify_executor_role  # noqa: E402
from app.services.catalog import load_catalog  # noqa: E402

DATASET = Path(__file__).parents[2] / "experiments" / "dataset" / "pilot_questions.jsonl"
QUESTIONS = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]


async def test_executor_role_is_unprivileged():
    assert await verify_executor_role() == "readonly_ai_executor"


async def test_catalog_loads_study_area():
    catalog = await load_catalog()
    assert catalog.categories[1] == "Coffee Shop"
    assert "BEJI" in catalog.districts and len(catalog.districts) == 11


@pytest.mark.parametrize("question", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
async def test_gold_sql_returns_rows(question):
    check = validate_sql(question["gold_sql"])
    assert check.valid, check.reason
    rows, _ = await execute_ai_sql(check.sql)
    assert rows


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT u.id FROM umkm.umkm u WHERE u.id = 1 FOR SHARE",
        "SELECT * FROM umkm.umkm WHERE false; UPDATE umkm.umkm SET rating = 5",
    ],
)
async def test_executor_cannot_write_or_lock(sql):
    with pytest.raises(DBAPIError):
        await execute_ai_sql(sql)
