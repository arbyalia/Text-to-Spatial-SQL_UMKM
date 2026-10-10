import pytest

from app.core.security import MAX_LIMIT, validate_sql, validate_user_query

GROUND_TRUTH = (
    "SELECT u.id, u.nama, ROUND(ST_Distance(u.location::geography, "
    "ST_SetSRID(ST_MakePoint(106.83178, -6.36043), 4326)::geography)::numeric, 2) AS jarak_meter "
    "FROM umkm.umkm AS u WHERE u.location IS NOT NULL AND u.jenis_umkm_id = 1 "
    "AND ST_DWithin(u.location::geography, ST_SetSRID(ST_MakePoint(106.83178, -6.36043), 4326)::geography, 500) "
    "ORDER BY jarak_meter ASC"
)


def test_ground_truth_passes_and_gets_limit():
    result = validate_sql(GROUND_TRUTH)
    assert result.valid
    assert result.sql.endswith("LIMIT 100")


@pytest.mark.parametrize(
    "sql",
    [
        GROUND_TRUTH,
        "WITH ref AS (SELECT d.location AS c FROM public.districts AS d WHERE d.name ILIKE '%beji%') "
        "SELECT u.id FROM umkm.umkm AS u, ref WHERE ST_DWithin(u.location::geography, ref.c::geography, 500)",
        "SELECT u.id FROM umkm.umkm AS u CROSS JOIN LATERAL (SELECT d.location AS center "
        "FROM public.districts AS d WHERE d.regency_id = 3276 LIMIT 1) AS ref "
        "ORDER BY u.location <-> ref.center LIMIT 3",
        "SELECT d.name, COUNT(*) FROM umkm.umkm AS u JOIN public.districts AS d ON d.id = u.district_id GROUP BY d.name",
        "SELECT u.id FROM umkm.umkm u WHERE ST_DWithin(u.location::geography, u.location::geography, 2 * 1000)",
    ],
)
def test_legitimate_queries_pass(sql):
    assert validate_sql(sql).valid


@pytest.mark.parametrize(
    "sql, reason",
    [
        ("SELECT 1 FROM umkm.umkm; DROP TABLE umkm.umkm", "multiple statements"),
        ("DELETE FROM umkm.umkm", "only SELECT"),
        ("UPDATE umkm.umkm SET rating = 5", "only SELECT"),
        ("DROP TABLE umkm.umkm", "only SELECT"),
        ("SELECT * FROM pg_catalog.pg_shadow", "table not allowed"),
        ("SELECT * FROM information_schema.tables", "table not allowed"),
        ("SELECT pg_sleep(10), u.id FROM umkm.umkm u", "function not allowed: pg_sleep"),
        ("SELECT pg_read_file('/etc/passwd') FROM umkm.umkm", "function not allowed"),
        ("SELECT set_config('role', 'postgres', false) FROM umkm.umkm", "function not allowed"),
        ("SELECT dblink('host=x', 'select 1') FROM umkm.umkm", "function not allowed"),
        ("SELECT * INTO umkm.copy FROM umkm.umkm", "SELECT INTO"),
        ("SELECT * FROM umkm.umkm FOR UPDATE", "locking"),
        ("SELECT 1", "no table"),
        (
            "SELECT u.id FROM umkm.umkm u WHERE ST_DWithin(u.location::geography, u.location::geography, 50000)",
            "radius",
        ),
        (
            "SELECT u.id FROM umkm.umkm u WHERE ST_DWithin(u.location::geography, u.location::geography, 10 * 1000)",
            "radius",
        ),
        ("SELECT u.id FROM umkm.umkm u UNION SELECT id FROM public.districts", "only SELECT"),
    ],
)
def test_dangerous_queries_blocked(sql, reason):
    result = validate_sql(sql)
    assert not result.valid
    assert result.status == "blocked_by_sanitizer"
    assert reason in result.reason


def test_invalid_syntax():
    assert validate_sql("SELEC id FROM").status == "invalid_sql_syntax"
    assert validate_sql("").status == "invalid_sql_syntax"


def test_limit_is_capped():
    result = validate_sql("SELECT u.id FROM umkm.umkm u LIMIT 1000000")
    assert result.valid
    assert result.sql.endswith(f"LIMIT {MAX_LIMIT}")
    assert validate_sql("SELECT u.id FROM umkm.umkm u LIMIT 5").sql.endswith("LIMIT 5")


def test_user_query_validation():
    assert validate_user_query("kopi dekat sini")
    assert not validate_user_query("   ")
    assert not validate_user_query("a" * 501)
