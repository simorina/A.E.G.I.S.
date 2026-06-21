import re


class UnsafeQueryError(Exception):
    """Query che viola i vincoli di sola lettura."""


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"COPY|CALL|DO|MERGE|VACUUM|REINDEX|REFRESH|COMMENT|EXECUTE)\b",
    re.IGNORECASE,
)
_TABLE_SCHEMA = re.compile(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)\.", re.IGNORECASE)
_SYSTEM = re.compile(r"\b(information_schema|pg_catalog|pg_[a-zA-Z_]+)\b", re.IGNORECASE)
_LEADING = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE)


def extract_sql(text: str) -> str:
    """Ripulisce l'output dell'LLM e ne estrae la prima statement eseguibile."""
    cleaned = re.sub(r"```sql|```", "", text, flags=re.IGNORECASE).strip()
    match = re.search(r"\b(WITH|SELECT)\b", cleaned, re.IGNORECASE)
    if match:
        cleaned = cleaned[match.start():]
    return cleaned.split(";")[0].strip()


def validate_readonly_sql(sql: str, allowed_schema: str) -> str:
    """Ritorna `sql` se è una singola query di sola lettura sullo schema consentito."""
    s = sql.strip()
    if not s:
        raise UnsafeQueryError("empty query")
    # Una sola statement: dopo aver tolto i ';' finali non deve restarne nessuno.
    if ";" in s.rstrip(";"):
        raise UnsafeQueryError("multiple statements are not allowed")
    if not _LEADING.match(s):
        raise UnsafeQueryError("only SELECT/WITH queries are allowed")
    if _FORBIDDEN.search(s):
        raise UnsafeQueryError("forbidden keyword detected")
    if _SYSTEM.search(s):
        raise UnsafeQueryError("system catalog access is not allowed")
    for schema in _TABLE_SCHEMA.findall(s):
        if schema.lower() != allowed_schema.lower():
            raise UnsafeQueryError(f"schema '{schema}' is not allowed")
    return s
