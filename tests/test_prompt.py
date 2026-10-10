from app.core.config import settings
from app.core.security import MAX_RADIUS_METER, validate_sql
from app.services.catalog import Catalog
from app.services.prompt import build_system_prompt, build_user_message, few_shot_examples

CATALOG = Catalog(categories={1: "Laundry", 7: "Coffee Shop"}, districts=["BEJI", "CINERE"])
NO_COFFEE = Catalog(categories={1: "Laundry"}, districts=["BEJI"])


def test_prompt_lists_categories_and_districts():
    prompt = build_system_prompt(CATALOG, "zero_shot")
    assert "1: Laundry" in prompt and "7: Coffee Shop" in prompt
    assert f"Radius maksimum {MAX_RADIUS_METER} meter" in prompt
    assert "BEJI, CINERE" in prompt
    assert "regency_id = 3276" in prompt
    assert "Contoh:" not in prompt


def test_few_shot_adds_examples():
    zero = build_system_prompt(CATALOG, "zero_shot")
    few = build_system_prompt(CATALOG, "few_shot")
    assert few.startswith(zero) and "Contoh:" in few


def test_few_shot_examples_pass_sanitizer():
    for catalog in (CATALOG, NO_COFFEE):
        for _, sql in few_shot_examples(catalog):
            assert validate_sql(sql).valid


def test_first_example_uses_few_shot_category():
    question, sql = few_shot_examples(CATALOG)[0]
    assert question.startswith("coffee shop dalam radius") and "u.jenis_umkm_id = 7 " in sql


def test_first_example_names_configured_category(monkeypatch):
    monkeypatch.setattr(settings, "FEW_SHOT_CATEGORY", "laundry")
    question, sql = few_shot_examples(CATALOG)[0]
    assert question.startswith("laundry dalam radius") and "u.jenis_umkm_id = 1 " in sql


def test_first_example_without_category():
    question, sql = few_shot_examples(NO_COFFEE)[0]
    assert question.startswith("UMKM ") and "jenis_umkm_id" not in sql
    assert "u.location IS NOT NULL AND ST_DWithin(" in sql


def test_aggregation_example_does_not_use_district_id():
    _, sql = few_shot_examples(CATALOG)[2]
    assert "district_id" not in sql and "JOIN umkm.jenis_umkm" in sql
    assert "GROUP BY j.nama" in sql and "::geography, 2000)" in sql


def test_user_message_carries_location():
    assert build_user_message("kopi", None, None) == "kopi"
    msg = build_user_message("kopi", -6.3, 106.8)
    assert "latitude -6.3" in msg and "longitude 106.8" in msg
