import pytest
from agent.safety import extract_sql, validate_readonly_sql, UnsafeQueryError


# --- extract_sql ---

def test_extract_strips_markdown_fences():
    raw = "```sql\nSELECT 1 AS geom\n```"
    assert extract_sql(raw) == "SELECT 1 AS geom"

def test_extract_anchors_on_select():
    raw = "Here is your query: SELECT name FROM schema1.parks"
    assert extract_sql(raw) == "SELECT name FROM schema1.parks"

def test_extract_keeps_only_first_statement():
    raw = "SELECT 1; DROP TABLE x"
    assert extract_sql(raw) == "SELECT 1"

def test_extract_anchors_on_with():
    raw = "WITH t AS (SELECT 1) SELECT * FROM t"
    assert extract_sql(raw).startswith("WITH t AS")


# --- validate_readonly_sql ---

def test_valid_select_passes():
    sql = "SELECT name, ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) AS geom FROM schema1.fermate_metro"
    assert validate_readonly_sql(sql, "schema1") == sql

def test_valid_with_passes():
    sql = "WITH m AS (SELECT * FROM schema1.fermate_metro) SELECT * FROM m"
    assert validate_readonly_sql(sql, "schema1") == sql

def test_geometry_mode_select_passes():
    sql = "SELECT 'AO' AS label, ST_SetSRID(ST_GeomFromText('POLYGON((9 45,9 46,10 46,9 45))'), 4326) AS geom"
    assert validate_readonly_sql(sql, "schema1") == sql

@pytest.mark.parametrize("sql", [
    "DROP TABLE schema1.parks",
    "DELETE FROM schema1.parks",
    "UPDATE schema1.parks SET name='x'",
    "INSERT INTO schema1.parks (name) VALUES ('x')",
    "ALTER TABLE schema1.parks ADD COLUMN c INT",
    "TRUNCATE schema1.parks",
    "GRANT ALL ON schema1.parks TO public",
])
def test_write_statements_rejected(sql):
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql(sql, "schema1")

def test_multiple_statements_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("SELECT 1; SELECT 2", "schema1")

def test_foreign_schema_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("SELECT * FROM otherschema.secrets", "schema1")

def test_system_catalog_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("SELECT * FROM information_schema.tables", "schema1")

def test_empty_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("   ", "schema1")
