from app.services.llm_service import parse_sql_response


def test_strict_json():
    r = parse_sql_response('{"sql": "SELECT 1"}')
    assert r.sql == "SELECT 1" and r.json_strict and r.error is None


def test_fenced_json_is_repaired_but_flagged():
    r = parse_sql_response('```json\n{"sql": "SELECT 1"}\n```')
    assert r.sql == "SELECT 1" and not r.json_strict


def test_invalid_outputs():
    for content in (None, "", "SELECT 1", '{"query": "SELECT 1"}', '{"sql": ""}', "[1, 2]"):
        assert parse_sql_response(content).error == "invalid_json"
