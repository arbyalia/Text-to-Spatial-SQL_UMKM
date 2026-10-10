import pytest

from app.core.security import MAX_LIMIT, validate_sql, validate_user_query

GROUND_TRUTH = (
    "SELECT u.id, u.nama, ROUND(ST_Distance(u.location::geography, "
    "ST_SetSRID(ST_MakePoint(106.83178, -6.36043), 4326)::geography)::numeric, 2) AS jarak_meter "
    "FROM umkm.umkm AS u WHERE u.location IS NOT NULL AND u.jenis_umkm_id = 1 "
    "AND ST_DWithin(u.location::geography, "
    "ST_SetSRID(ST_MakePoint(106.83178, -6.36043), 4326)::geography, 500) "
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
        "WITH ref AS (SELECT d.location AS c FROM public.districts AS d "
        "WHERE d.name ILIKE '%beji%') "
        "SELECT u.id FROM umkm.umkm AS u, ref "
        "WHERE ST_DWithin(u.location::geography, ref.c::geography, 500)",
        "SELECT u.id FROM umkm.umkm AS u CROSS JOIN LATERAL (SELECT d.location AS center "
        "FROM public.districts AS d WHERE d.regency_id = 3276 LIMIT 1) AS ref "
        "ORDER BY u.location <-> ref.center LIMIT 3",
        "SELECT d.name, COUNT(*) FROM umkm.umkm AS u "
        "JOIN public.districts AS d ON d.id = u.district_id GROUP BY d.name",
        "SELECT u.id FROM umkm.umkm u "
        "WHERE ST_DWithin(u.location::geography, u.location::geography, 2 * 1000)",
        "SELECT u.id FROM umkm.umkm u "
        "WHERE ST_DWithin(geography(u.location), CAST(u.location AS geography), 5000)",
        "SELECT u.id FROM umkm.umkm u "
        "WHERE ST_Distance(u.location::geography, u.location::geography) < 1500",
        "SELECT u.id FROM umkm.umkm u "
        "WHERE ST_Distance(u.location::geography, u.location::geography) <= 2.5 * 1000",
        "SELECT u.id FROM umkm.umkm u "
        "WHERE ST_Distance(u.location::geography, u.location::geography) BETWEEN 100 AND 5000",
        "SELECT u.id, ST_Distance(u.location, u.location) AS d FROM umkm.umkm u ORDER BY d",
        "SELECT u.id FROM umkm.umkm u UNION SELECT d.id FROM public.districts d",
        "SELECT u.id FROM umkm.umkm u UNION ALL SELECT u.id FROM umkm.umkm u",
        "SELECT u.id FROM umkm.umkm u WHERE u.rating > 4 "
        "INTERSECT SELECT u.id FROM umkm.umkm u "
        "WHERE ST_DWithin(u.location::geography, u.location::geography, 1000)",
        "SELECT u.id FROM umkm.umkm u EXCEPT SELECT u.id FROM umkm.umkm u WHERE u.rating < 3",
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
        ("WITH d AS (DELETE FROM umkm.umkm RETURNING id) SELECT id FROM d", "only SELECT"),
        (
            "WITH d AS (UPDATE umkm.umkm SET rating = 5 RETURNING id) SELECT id FROM d",
            "only SELECT",
        ),
        (
            "WITH d AS (INSERT INTO umkm.umkm (nama) VALUES ('x') RETURNING id) SELECT id FROM d",
            "only SELECT",
        ),
        ("SELECT * INTO umkm.copy FROM umkm.umkm", "SELECT INTO"),
        ("SELECT * FROM umkm.umkm FOR UPDATE", "locking"),
        ("SELECT 1", "no table"),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_DWithin(u.location::geography, u.location::geography, 50000)",
            "radius",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_DWithin(u.location::geography, u.location::geography, 10 * 1000)",
            "radius",
        ),
        (
            "SELECT u.id FROM umkm.umkm u WHERE ST_DWithin(u.location, u.location, 500)",
            "ST_DWithin must use geography",
        ),
        (
            "SELECT u.id FROM umkm.umkm u WHERE ST_DWithin(u.location::geography, u.location, 500)",
            "ST_DWithin must use geography",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_DWithin(u.location::geometry, u.location::geometry, 0.5)",
            "ST_DWithin must use geography",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_DWithin(u.location::geography, u.location::geography, u.rating * 100000)",
            "radius must be a numeric constant",
        ),
        (
            "SELECT u.id FROM umkm.umkm u WHERE ST_DWithin(u.location::geography, "
            "u.location::geography, (SELECT 99999 FROM umkm.umkm LIMIT 1))",
            "radius must be a numeric constant",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_DWithin(u.location::geography, u.location::geography, 5000 + 1)",
            "radius",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_Distance(u.location::geography, u.location::geography) < 10000",
            "radius exceeds",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_Distance(u.location::geography, u.location::geography) <= 5 * 1001",
            "radius exceeds",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_Distance(u.location::geography, u.location::geography) BETWEEN 0 AND 9000",
            "radius exceeds",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE 9000 > ST_Distance(u.location::geography, u.location::geography)",
            "radius exceeds",
        ),
        (
            "SELECT u.id FROM umkm.umkm u "
            "WHERE ST_Distance(u.location::geography, u.location::geography) < u.rating * 1e6",
            "radius must be a numeric constant",
        ),
        (
            "SELECT u.id FROM umkm.umkm u WHERE ST_Distance(u.location, u.location) < 0.01",
            "ST_Distance must use geography",
        ),
        (
            "SELECT u.jenis_umkm_id FROM umkm.umkm u GROUP BY u.jenis_umkm_id "
            "HAVING MIN(ST_Distance(u.location::geography, u.location::geography)) < 1 "
            "AND ST_Distance(MIN(u.location)::geography, MIN(u.location)::geography) < 20000",
            "radius exceeds",
        ),
        (
            "SELECT u.id FROM umkm.umkm u UNION SELECT pg_sleep(1) FROM umkm.umkm",
            "function not allowed",
        ),
        (
            "SELECT u.id FROM umkm.umkm u UNION ALL SELECT usename FROM pg_catalog.pg_user",
            "table not allowed",
        ),
        (
            "SELECT u.id FROM umkm.umkm u EXCEPT SELECT u.id FROM umkm.umkm u "
            "WHERE ST_DWithin(u.location::geography, u.location::geography, 50000)",
            "radius",
        ),
        (
            "SELECT u.id FROM umkm.umkm u UNION SELECT u.id FROM umkm.umkm u FOR UPDATE",
            "locking",
        ),
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


def test_set_operation_limit_is_outermost():
    sql = validate_sql("SELECT u.id FROM umkm.umkm u UNION SELECT d.id FROM public.districts d").sql
    assert sql.endswith("UNION SELECT d.id FROM public.districts AS d LIMIT 100")
    capped = validate_sql(
        "SELECT u.id FROM umkm.umkm u UNION ALL SELECT u.id FROM umkm.umkm u LIMIT 100000"
    )
    assert capped.sql.endswith(f"LIMIT {MAX_LIMIT}") and capped.sql.count("LIMIT") == 1


def test_user_query_validation():
    assert validate_user_query("kopi dekat sini")
    assert not validate_user_query("   ")
    assert not validate_user_query("a" * 501)
