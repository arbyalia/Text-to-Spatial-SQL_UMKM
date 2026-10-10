from app.core.security import validate_sql
from app.services.catalog import Catalog
from app.services.prompt import FEW_SHOT_EXAMPLES, build_system_prompt, build_user_message

CATALOG = Catalog(categories={1: "Coffee Shop", 2: "Laundry"}, districts=["BEJI", "CINERE"])


def test_prompt_lists_categories_and_districts():
    prompt = build_system_prompt(CATALOG, "zero_shot")
    assert "1: Coffee Shop" in prompt and "2: Laundry" in prompt
    assert "BEJI, CINERE" in prompt
    assert "regency_id = 3276" in prompt
    assert "Contoh:" not in prompt


def test_few_shot_adds_examples():
    zero = build_system_prompt(CATALOG, "zero_shot")
    few = build_system_prompt(CATALOG, "few_shot")
    assert few.startswith(zero) and "Contoh:" in few


def test_few_shot_examples_pass_sanitizer():
    for _, sql in FEW_SHOT_EXAMPLES:
        assert validate_sql(sql.format(coffee_id=1, regency_id=3276)).valid


def test_user_message_carries_location():
    assert build_user_message("kopi", None, None) == "kopi"
    msg = build_user_message("kopi", -6.3, 106.8)
    assert "latitude -6.3" in msg and "longitude 106.8" in msg
