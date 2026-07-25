# A.E.G.I.S. Agent Tool-Calling Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sostituire `agent.py` monolitico con un package `agent/` a tool-calling, sicuro (SQL read-only a doppio strato), con memoria conversazionale end-to-end e copertura di test sulle funzioni pure.

**Architecture:** Un orchestratore lega tool distinti al modello (`bind_tools`); ogni tool ha un prompt focalizzato. La SQL generata passa per un validatore read-only ed è eseguita in transazione `READ ONLY` con `statement_timeout`. La memoria è un store in-memory per `session_id`, passato dal frontend.

**Tech Stack:** Python 3.10+, FastAPI, LangChain (`langchain-core`, `langchain-community`, `langchain-ollama`), SQLAlchemy, GeoPandas, PostGIS, pytest.

## Global Constraints

- **Schema sorgente:** ogni accesso DB usa `Config.SCHEMA` (default env `TARGET_SCHEMA=schema1`). Mai hardcodare `schema1` nel codice o nei prompt — iniettarlo.
- **Colonna geometria:** ogni risultato cartografabile espone una colonna `geom` in **SRID 4326** (l'API legge `geom_col='geom'`).
- **Sola lettura:** nessuna query che non sia `SELECT`/`WITH` può essere eseguita. Doppio strato: validazione statica + transazione DB `READ ONLY`.
- **Determinismo LLM:** tutti i `ChatOllama` di testo usano `temperature=0`.
- **No nuove dipendenze pesanti:** niente LangGraph. Solo i primitivi LangChain già in uso + `pytest`.
- **Branch di lavoro:** `feature/agent-toolcalling-refactor` (già creato).
- **Comando test:** dalla root del progetto → `python -m pytest tests/ -v`.

---

## File Structure

**Create:**
- `requirements.txt` — dipendenze pinnabili del progetto.
- `tests/__init__.py`, `tests/conftest.py` — setup pytest.
- `agent/__init__.py` — wiring + API pubblica (`engine`, `run`, `analyze_satellite_image`, `vision_llm`, `config`).
- `agent/config.py` — `Config`, `load_config`, `ConfigError`.
- `agent/safety.py` — `extract_sql`, `validate_readonly_sql`, `UnsafeQueryError`.
- `agent/memory.py` — `ConversationMemory`.
- `agent/prompts.py` — prompt spezzati (system, sql_query, geometry, vision, briefing).
- `agent/db.py` — `make_engine`, `make_sql_database`, `get_table_info`, `readonly_preamble`, `execute_readonly`.
- `agent/llm.py` — `build_text_llm`, `build_vision_llm`.
- `agent/vision.py` — `build_vision_message`, `analyze_satellite_image`.
- `agent/tools.py` — `make_tools`.
- `agent/orchestrator.py` — `Orchestrator`, `keyword_router`.
- `tests/test_config.py`, `tests/test_safety.py`, `tests/test_memory.py`, `tests/test_prompts.py`, `tests/test_db.py`, `tests/test_vision.py`, `tests/test_tools.py`, `tests/test_orchestrator.py`.

**Modify:**
- `server.py` — endpoint sottili, `ChatRequest.session_id`.
- `js/script.js` — genera e invia `session_id`.
- `.env` — nuove var opzionali documentate.
- `README.md` — nota su package/import/env.

**Delete:**
- `agent.py` — sostituito dal package `agent/`.

> **Nota transizione:** dopo il Task 1, `server.py` resta temporaneamente rotto (importa `from agent import ...` che cambia) finché il Task 10 non lo riallinea. Accettabile sul branch: i test non importano `server.py`.

---

## Task 1: Scaffolding + Config

**Files:**
- Create: `requirements.txt`, `tests/__init__.py`, `tests/conftest.py`, `agent/__init__.py` (placeholder), `agent/config.py`
- Test: `tests/test_config.py`
- Delete: `agent.py`

**Interfaces:**
- Produces: `agent.config.load_config(env: Mapping[str,str] | None = None) -> Config`; `Config` (frozen dataclass) con campi `db_uri, schema, llm_url, text_model, vision_model, statement_timeout_ms: int, memory_turns: int, top_k: int, tool_calling: bool`; `ConfigError(Exception)`.

- [ ] **Step 1: Rimuovi il vecchio modulo e crea lo scaffolding**

```bash
git rm agent.py
mkdir -p agent tests
```

Create `requirements.txt`:

```text
fastapi
uvicorn
geopandas
sqlalchemy
psycopg2-binary
langchain
langchain-core
langchain-community
langchain-ollama
contextily
pillow
python-dotenv
pytest
```

Create `tests/__init__.py` (vuoto) e `tests/conftest.py`:

```python
import os
import sys

# Garantisce che la root del progetto sia importabile (package `agent`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

Create `agent/__init__.py` (placeholder, verrà riempito nel Task 9):

```python
"""A.E.G.I.S. agent package."""
```

- [ ] **Step 2: Scrivi i test di config (devono fallire)**

Create `tests/test_config.py`:

```python
import pytest
from agent.config import load_config, Config, ConfigError

BASE_ENV = {
    "DB_USER": "postgres", "DB_PASS": "secret", "DB_HOST": "localhost",
    "DB_PORT": "5432", "DB_NAME": "aegis", "TARGET_SCHEMA": "schema1",
    "LLM_URL": "http://localhost:11434", "MODEL_NAME": "nemotron",
}

def test_loads_valid_config():
    cfg = load_config(BASE_ENV)
    assert isinstance(cfg, Config)
    assert cfg.schema == "schema1"
    assert cfg.db_uri == "postgresql://postgres:secret@localhost:5432/aegis"

def test_models_fallback_to_model_name():
    cfg = load_config(BASE_ENV)
    assert cfg.text_model == "nemotron"
    assert cfg.vision_model == "nemotron"

def test_explicit_models_override_fallback():
    env = {**BASE_ENV, "TEXT_MODEL": "qwen", "VISION_MODEL": "llava"}
    cfg = load_config(env)
    assert cfg.text_model == "qwen"
    assert cfg.vision_model == "llava"

def test_missing_required_var_raises():
    env = {k: v for k, v in BASE_ENV.items() if k != "DB_HOST"}
    with pytest.raises(ConfigError):
        load_config(env)

def test_no_model_configured_raises():
    env = {k: v for k, v in BASE_ENV.items() if k != "MODEL_NAME"}
    with pytest.raises(ConfigError):
        load_config(env)

def test_defaults_for_optional_numbers():
    cfg = load_config(BASE_ENV)
    assert cfg.statement_timeout_ms == 5000
    assert cfg.memory_turns == 6
    assert cfg.top_k == 100
    assert cfg.tool_calling is True

def test_tool_calling_can_be_disabled():
    env = {**BASE_ENV, "AGENT_TOOL_CALLING": "off"}
    assert load_config(env).tool_calling is False
```

- [ ] **Step 3: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.config'`.

- [ ] **Step 4: Implementa `agent/config.py`**

```python
import os
from dataclasses import dataclass
from typing import Mapping, Optional


class ConfigError(Exception):
    """Configurazione mancante o non valida."""


_REQUIRED = ("DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
             "TARGET_SCHEMA", "LLM_URL")


@dataclass(frozen=True)
class Config:
    db_uri: str
    schema: str
    llm_url: str
    text_model: str
    vision_model: str
    statement_timeout_ms: int
    memory_turns: int
    top_k: int
    tool_calling: bool


def load_config(env: Optional[Mapping[str, str]] = None) -> Config:
    env = os.environ if env is None else env

    missing = [k for k in _REQUIRED if not env.get(k)]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")

    base_model = env.get("MODEL_NAME", "")
    text_model = env.get("TEXT_MODEL") or base_model
    vision_model = env.get("VISION_MODEL") or base_model
    if not text_model:
        raise ConfigError("No TEXT_MODEL or MODEL_NAME configured")
    if not vision_model:
        raise ConfigError("No VISION_MODEL or MODEL_NAME configured")

    db_uri = (f"postgresql://{env['DB_USER']}:{env['DB_PASS']}@"
              f"{env['DB_HOST']}:{env['DB_PORT']}/{env['DB_NAME']}")

    return Config(
        db_uri=db_uri,
        schema=env["TARGET_SCHEMA"],
        llm_url=env["LLM_URL"],
        text_model=text_model,
        vision_model=vision_model,
        statement_timeout_ms=int(env.get("STATEMENT_TIMEOUT_MS", "5000")),
        memory_turns=int(env.get("MEMORY_TURNS", "6")),
        top_k=int(env.get("TOP_K", "100")),
        tool_calling=env.get("AGENT_TOOL_CALLING", "on").strip().lower() != "off",
    )
```

- [ ] **Step 5: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/ agent/ && git rm --cached agent.py 2>/dev/null; git add -A
git commit -m "feat(agent): scaffolding package + config con validazione e fallback modelli"
```

---

## Task 2: Safety (validazione SQL read-only)

**Files:**
- Create: `agent/safety.py`
- Test: `tests/test_safety.py`

**Interfaces:**
- Produces: `extract_sql(text: str) -> str`; `validate_readonly_sql(sql: str, allowed_schema: str) -> str` (ritorna la query se sicura, altrimenti solleva); `UnsafeQueryError(Exception)`.

- [ ] **Step 1: Scrivi i test di safety (devono fallire)**

Create `tests/test_safety.py`:

```python
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
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_safety.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.safety'`.

- [ ] **Step 3: Implementa `agent/safety.py`**

```python
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
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_safety.py -v`
Expected: PASS (tutti i casi parametrizzati inclusi).

- [ ] **Step 5: Commit**

```bash
git add agent/safety.py tests/test_safety.py
git commit -m "feat(agent): guardrail SQL read-only (validate + extract)"
```

---

## Task 3: Memory (store conversazionale)

**Files:**
- Create: `agent/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Produces: `ConversationMemory(max_turns: int = 6)` con `append(session_id: str, role: str, content: str) -> None`, `get(session_id: str) -> list[tuple[str, str]]`, `clear(session_id: str) -> None`. Un "turn" = una coppia (utente, assistente) → cap interno `max_turns * 2` messaggi.

- [ ] **Step 1: Scrivi i test (devono fallire)**

Create `tests/test_memory.py`:

```python
from agent.memory import ConversationMemory

def test_append_and_get_in_order():
    m = ConversationMemory(max_turns=6)
    m.append("s1", "user", "ciao")
    m.append("s1", "assistant", "ack")
    assert m.get("s1") == [("user", "ciao"), ("assistant", "ack")]

def test_sessions_are_isolated():
    m = ConversationMemory()
    m.append("a", "user", "x")
    m.append("b", "user", "y")
    assert m.get("a") == [("user", "x")]
    assert m.get("b") == [("user", "y")]

def test_unknown_session_returns_empty():
    assert ConversationMemory().get("nope") == []

def test_cap_keeps_most_recent():
    m = ConversationMemory(max_turns=1)  # cap = 2 messaggi
    m.append("s", "user", "1")
    m.append("s", "assistant", "2")
    m.append("s", "user", "3")
    assert m.get("s") == [("assistant", "2"), ("user", "3")]

def test_clear_removes_session():
    m = ConversationMemory()
    m.append("s", "user", "x")
    m.clear("s")
    assert m.get("s") == []
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_memory.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.memory'`.

- [ ] **Step 3: Implementa `agent/memory.py`**

```python
from collections import deque
from typing import Deque, Dict, List, Tuple

Turn = Tuple[str, str]


class ConversationMemory:
    """Store in-memory della cronologia per sessione, con cap sugli ultimi turni."""

    def __init__(self, max_turns: int = 6):
        self._max_messages = max(1, max_turns) * 2
        self._store: Dict[str, Deque[Turn]] = {}

    def append(self, session_id: str, role: str, content: str) -> None:
        buf = self._store.get(session_id)
        if buf is None:
            buf = deque(maxlen=self._max_messages)
            self._store[session_id] = buf
        buf.append((role, content))

    def get(self, session_id: str) -> List[Turn]:
        return list(self._store.get(session_id, []))

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_memory.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/memory.py tests/test_memory.py
git commit -m "feat(agent): memoria conversazionale per session_id"
```

---

## Task 4: Prompts (spezzati)

**Files:**
- Create: `agent/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Produces: `AGENT_SYSTEM_PROMPT: str`; `VISION_PROMPT: str`; `BRIEFING_TEMPLATE: str` (placeholder `{data_summary}`); `GEOMETRY_TEMPLATE: str` (placeholder `{request}`, `{error}`); `sql_query_template(schema: str) -> str` (placeholder `{table_info}`, `{question}`, `{error}`, schema iniettato).

- [ ] **Step 1: Scrivi i test (devono fallire)**

Create `tests/test_prompts.py`:

```python
from agent import prompts

def test_sql_template_injects_schema():
    t = prompts.sql_query_template("myschema")
    assert "myschema" in t
    assert "schema1" not in t  # nessun hardcode residuo
    for ph in ("{table_info}", "{question}", "{error}"):
        assert ph in t

def test_geometry_template_has_placeholders():
    assert "{request}" in prompts.GEOMETRY_TEMPLATE
    assert "{error}" in prompts.GEOMETRY_TEMPLATE
    assert "ST_" in prompts.GEOMETRY_TEMPLATE  # parla di costruttori PostGIS

def test_briefing_template_has_placeholder():
    assert "{data_summary}" in prompts.BRIEFING_TEMPLATE

def test_system_prompt_mentions_tools_and_geom():
    p = prompts.AGENT_SYSTEM_PROMPT.lower()
    assert "geom" in p
    assert "4326" in prompts.AGENT_SYSTEM_PROMPT
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: FAIL con `AttributeError`/`ImportError` su `agent.prompts`.

- [ ] **Step 3: Implementa `agent/prompts.py`**

```python
AGENT_SYSTEM_PROMPT = """\
IDENTITY: You are **Palantir**, the GEOINT engine of A.E.G.I.S., reporting to a field operator over a PostGIS database for the city of Milan.

You have tools. Choose the right one for the operator's request:
- `query_intel`  -> when they want REAL intel ALREADY in the database (find / locate / list / count / analyze metro stations, parks, hospitals, infrastructure).
- `draw_geometry` -> when they want to DRAW / CREATE / MARK / TRACE / DEFINE a NEW shape on the map (patrol zone, perimeter, area of operations, corridor, route, buffer). This does NOT read the database.

After a tool runs, deliver a short, factual, tactical briefing based ONLY on the tool's output. Never invent intel.

Every map result exposes a geometry column named `geom` in SRID 4326.
"""

VISION_PROMPT = """\
IDENTITY: You are Palantir, a GEOINT analysis agent running optical reconnaissance.
TASK: Analyze this image or screenshot provided by the operator.
OUTPUT: Provide a brief operational report covering:
1. Urban Density (High/Medium/Low).
2. Key Infrastructure (Roads, Rails, Water bodies).
3. Potential Obstacles or Cover.

Keep it concise and actionable.
"""

BRIEFING_TEMPLATE = """\
You are **Palantir**, a military GEOINT agent reporting to a field operator.
Tool output:
{data_summary}

Write a short, factual, tactical-style briefing based ONLY on the data above.
Be concise and operational; never invent intel that is not present.
Response:
"""

GEOMETRY_TEMPLATE = """\
### IDENTITY
You are **Palantir**. Synthesize ONE PostgreSQL/PostGIS SELECT that BUILDS a new geometry
(patrol zone, perimeter, corridor, route, buffer) from the operator's description.
Output the SQL only -- no prose, no markdown fences.

### HARD CONSTRAINTS
1. Emit ONE single SELECT statement. Do NOT query any table.
2. Build geometry with PostGIS constructors: ST_GeomFromText, ST_MakePoint, ST_MakeLine, ST_MakePolygon, ST_Buffer.
3. The result MUST expose a geometry column named exactly `geom`, wrapped in ST_SetSRID(..., 4326).
4. Polygons use 'POLYGON((lon lat, ...))' and MUST close the ring (last point = first). Lines use 'LINESTRING(lon lat, ...)'.
5. You MAY add a descriptive text label column.

### EXAMPLES
- Area of operations (polygon):
  SELECT 'AO_ALPHA' AS label,
         ST_SetSRID(ST_GeomFromText('POLYGON((9.18 45.46, 9.20 45.46, 9.20 45.48, 9.18 45.48, 9.18 45.46))'), 4326) AS geom
- Infiltration route (line):
  SELECT 'ROUTE_1' AS label,
         ST_SetSRID(ST_GeomFromText('LINESTRING(9.18 45.46, 9.19 45.47, 9.21 45.46)'), 4326) AS geom
- 500 m security radius:
  SELECT 'RADIUS_500M' AS label,
         ST_Buffer(ST_SetSRID(ST_MakePoint(9.19, 45.464), 4326)::geography, 500)::geometry AS geom

### ERROR CORRECTION
PREVIOUS ERROR: {error}
If the error is not empty, rewrite the query to fix the specific issue.

### REQUEST
{request}

### SQL
"""

_SQL_QUERY_TEMPLATE = """\
### IDENTITY
You are **Palantir**, querying a PostGIS PostgreSQL database for the city of Milan.
Convert the operator's request into ONE valid, executable PostgreSQL/PostGIS SELECT.
Output the SQL only -- no prose, no markdown fences.

### HARD CONSTRAINTS
1. Emit ONE single SELECT statement.
2. The result MUST expose a geometry column named exactly `geom` in SRID 4326.
3. ALWAYS prefix tables with the schema name -> use {schema} (e.g. {schema}.fermate_metro).
4. NEVER hallucinate columns. Use ONLY the columns defined in the schema below.
5. The `parks` table already has a `geom` column -> select it directly AS geom.
6. Tables with NO geom column -> build it as ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) AS geom.

### DATABASE SCHEMA
{table_info}

### EXAMPLES
- All metro stations on line M4:
  SELECT name, line, ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) AS geom
  FROM {schema}.fermate_metro WHERE line = 'M4'
- All parks:
  SELECT name, area_sqm, geom FROM {schema}.parks

### ERROR CORRECTION
PREVIOUS ERROR: {error}
If the error is not empty, rewrite the query to fix the specific issue.

### REQUEST
{question}

### SQL
"""


def sql_query_template(schema: str) -> str:
    """Template MODE 1 con lo schema iniettato; lascia liberi {table_info},{question},{error}."""
    return _SQL_QUERY_TEMPLATE.replace("{schema}", schema)
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/prompts.py tests/test_prompts.py
git commit -m "feat(agent): prompt spezzati (system/sql/geometry/vision/briefing)"
```

---

## Task 5: DB layer (esecuzione read-only)

**Files:**
- Create: `agent/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `make_engine(db_uri: str)`; `make_sql_database(db_uri: str, schema: str)`; `get_table_info(sql_db) -> str`; `readonly_preamble(statement_timeout_ms: int) -> list[str]`; `execute_readonly(engine, sql: str, statement_timeout_ms: int, geom_col: str = "geom")` → GeoDataFrame.

- [ ] **Step 1: Scrivi il test della parte pura (deve fallire)**

Create `tests/test_db.py`:

```python
from agent.db import readonly_preamble

def test_preamble_sets_timeout_and_readonly():
    stmts = readonly_preamble(5000)
    assert "SET statement_timeout = 5000" in stmts
    assert "SET default_transaction_read_only = on" in stmts

def test_preamble_coerces_to_int():
    # Difesa: niente iniezione tramite timeout non numerico.
    stmts = readonly_preamble(1234)
    assert any("1234" in s for s in stmts)
    assert all(";" not in s for s in stmts)
```

- [ ] **Step 2: Esegui il test per verificare che fallisca**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.db'`.

- [ ] **Step 3: Implementa `agent/db.py`**

```python
import logging
from typing import List

import geopandas as gpd
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase

log = logging.getLogger(__name__)


def make_engine(db_uri: str):
    return create_engine(db_uri)


def make_sql_database(db_uri: str, schema: str) -> SQLDatabase:
    return SQLDatabase.from_uri(db_uri, schema=schema)


def get_table_info(sql_db: SQLDatabase) -> str:
    return sql_db.get_table_info()


def readonly_preamble(statement_timeout_ms: int) -> List[str]:
    """Statement di sessione che forzano sola-lettura e timeout (int coerciti)."""
    return [
        f"SET statement_timeout = {int(statement_timeout_ms)}",
        "SET default_transaction_read_only = on",
    ]


def execute_readonly(engine, sql: str, statement_timeout_ms: int, geom_col: str = "geom"):
    """Esegue una SELECT in una connessione forzata read-only e ritorna un GeoDataFrame."""
    with engine.connect() as conn:
        for stmt in readonly_preamble(statement_timeout_ms):
            conn.execute(text(stmt))
        gdf = gpd.read_postgis(text(sql), con=conn, geom_col=geom_col)
    log.info("execute_readonly: %d rows", len(gdf))
    return gdf
```

- [ ] **Step 4: Esegui il test (deve passare)**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/db.py tests/test_db.py
git commit -m "feat(agent): db layer con esecuzione read-only + timeout"
```

---

## Task 6: LLM factory + Vision

**Files:**
- Create: `agent/llm.py`, `agent/vision.py`
- Test: `tests/test_vision.py`

**Interfaces:**
- Produces: `agent.llm.build_text_llm(config)`, `agent.llm.build_vision_llm(config)` (ChatOllama, temperature 0); `agent.vision.build_vision_message(image_b64: str, mime_type: str, operator_context: str, prompt: str = VISION_PROMPT) -> HumanMessage`; `agent.vision.analyze_satellite_image(llm, image_data: bytes, operator_context: str = "", mime_type: str = "image/jpeg") -> str`.

- [ ] **Step 1: Scrivi i test vision (devono fallire)**

Create `tests/test_vision.py`:

```python
from agent.vision import build_vision_message, analyze_satellite_image

def test_message_has_text_and_image_parts():
    msg = build_vision_message("QUJD", "image/png", "")
    parts = msg.content
    assert parts[0]["type"] == "text"
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"] == "data:image/png;base64,QUJD"

def test_operator_context_is_appended():
    msg = build_vision_message("QUJD", "image/jpeg", "look north")
    assert "look north" in msg.content[0]["text"]

def test_no_context_keeps_base_prompt_only():
    msg = build_vision_message("QUJD", "image/jpeg", "   ")
    assert "OPERATOR NOTE" not in msg.content[0]["text"]

def test_analyze_uses_injected_llm():
    class FakeLLM:
        def invoke(self, messages):
            class R: content = "RECON OK"
            return R()
    out = analyze_satellite_image(FakeLLM(), b"ABC", "ctx", "image/jpeg")
    assert out == "RECON OK"
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_vision.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.vision'`.

- [ ] **Step 3: Implementa `agent/llm.py` e `agent/vision.py`**

`agent/llm.py`:

```python
from langchain_ollama import ChatOllama


def build_text_llm(config):
    return ChatOllama(model=config.text_model, temperature=0, base_url=config.llm_url)


def build_vision_llm(config):
    return ChatOllama(model=config.vision_model, temperature=0, base_url=config.llm_url)
```

`agent/vision.py`:

```python
import base64

from langchain_core.messages import HumanMessage

from .prompts import VISION_PROMPT


def build_vision_message(image_b64: str, mime_type: str, operator_context: str,
                         prompt: str = VISION_PROMPT) -> HumanMessage:
    text = prompt
    if operator_context and operator_context.strip():
        text += f"\nOPERATOR NOTE: {operator_context.strip()}"
    return HumanMessage(content=[
        {"type": "text", "text": text},
        {"type": "image_url",
         "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
    ])


def analyze_satellite_image(llm, image_data: bytes, operator_context: str = "",
                            mime_type: str = "image/jpeg") -> str:
    img_b64 = base64.b64encode(image_data).decode("utf-8")
    message = build_vision_message(img_b64, mime_type, operator_context)
    return llm.invoke([message]).content
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_vision.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/llm.py agent/vision.py tests/test_vision.py
git commit -m "feat(agent): factory modelli (testo+vision) e analisi immagine iniettabile"
```

---

## Task 7: Tools (query_intel, draw_geometry)

**Files:**
- Create: `agent/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `agent.safety.extract_sql`, `agent.safety.validate_readonly_sql`, `agent.safety.UnsafeQueryError`.
- Produces: `make_tools(*, generate_query_sql, generate_geometry_sql, execute_sql, schema: str, ctx: dict, max_attempts: int = 3) -> list` — lista di tool LangChain (`.name`, `.invoke`). I tool hanno firma `(request: str) -> str` e nomi `query_intel`, `draw_geometry`. Effetto collaterale: scrivono il GeoJSON in `ctx["geojson"]`.
  - `generate_query_sql(request: str, error: str) -> str`, `generate_geometry_sql(request: str, error: str) -> str`, `execute_sql(sql: str) -> GeoDataFrame-like` (con `.empty`, `.to_json()`, `.drop(columns=..., errors="ignore").to_string()`).

- [ ] **Step 1: Scrivi i test dei tool (devono fallire)**

Create `tests/test_tools.py`:

```python
import pytest
from agent.tools import make_tools


class FakeGDF:
    def __init__(self, empty=False):
        self.empty = empty
    def to_json(self):
        return '{"type":"FeatureCollection","features":[]}'
    def drop(self, columns=None, errors=None):
        return self
    def to_string(self):
        return "name\nDuomo"


def _tools(ctx, gen_q=None, gen_g=None, execute=None, max_attempts=3):
    return {t.name: t for t in make_tools(
        generate_query_sql=gen_q or (lambda request, error: "SELECT 1 AS geom"),
        generate_geometry_sql=gen_g or (lambda request, error: "SELECT 'L' AS label, 1 AS geom"),
        execute_sql=execute or (lambda sql: FakeGDF()),
        schema="schema1",
        ctx=ctx,
        max_attempts=max_attempts,
    )}


def test_query_intel_success_sets_geojson():
    ctx = {"geojson": None}
    tools = _tools(ctx,
                   gen_q=lambda request, error: "SELECT name FROM schema1.fermate_metro",
                   execute=lambda sql: FakeGDF())
    out = tools["query_intel"].invoke({"request": "list metro"})
    assert "Duomo" in out
    assert ctx["geojson"] is not None

def test_query_intel_blocks_unsafe_and_never_executes():
    ctx = {"geojson": None}
    calls = []
    tools = _tools(ctx,
                   gen_q=lambda request, error: "DROP TABLE schema1.parks",
                   execute=lambda sql: calls.append(sql) or FakeGDF())
    out = tools["query_intel"].invoke({"request": "wipe"})
    assert "DENIED" in out
    assert calls == []

def test_query_intel_retries_then_succeeds():
    ctx = {"geojson": None}
    state = {"n": 0}
    def execute(sql):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("syntax error")
        return FakeGDF()
    tools = _tools(ctx,
                   gen_q=lambda request, error: "SELECT name FROM schema1.parks",
                   execute=execute)
    out = tools["query_intel"].invoke({"request": "parks"})
    assert "Duomo" in out
    assert state["n"] == 2

def test_query_intel_empty_result_message():
    ctx = {"geojson": None}
    tools = _tools(ctx, execute=lambda sql: FakeGDF(empty=True))
    out = tools["query_intel"].invoke({"request": "x"})
    assert "No tactical data" in out
    assert ctx["geojson"] is None

def test_draw_geometry_sets_geojson():
    ctx = {"geojson": None}
    tools = _tools(ctx,
                   gen_g=lambda request, error: "SELECT 'AO' AS label, 1 AS geom",
                   execute=lambda sql: FakeGDF())
    out = tools["draw_geometry"].invoke({"request": "draw a zone"})
    assert ctx["geojson"] is not None
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.tools'`.

- [ ] **Step 3: Implementa `agent/tools.py`**

```python
import logging

from langchain_core.tools import tool

from .safety import extract_sql, validate_readonly_sql, UnsafeQueryError

log = logging.getLogger(__name__)


def make_tools(*, generate_query_sql, generate_geometry_sql, execute_sql,
               schema, ctx, max_attempts=3):
    """Crea i tool legabili al modello; scrivono il GeoJSON prodotto in ctx['geojson']."""

    def _run_sql_pipeline(generate, request, label):
        error = ""
        for attempt in range(max_attempts):
            raw = generate(request=request, error=error)
            sql = extract_sql(raw)
            if not sql:
                error = "the generated query was empty"
                continue
            try:
                validate_readonly_sql(sql, schema)
            except UnsafeQueryError as exc:
                log.warning("%s blocked unsafe SQL: %s", label, exc)
                return f"REQUEST_DENIED: unsafe query blocked ({exc})."
            try:
                gdf = execute_sql(sql)
            except Exception as exc:  # noqa: BLE001 - error fed back to the LLM
                error = str(exc)
                log.warning("%s attempt %d failed: %s", label, attempt + 1, exc)
                continue
            if gdf.empty:
                return "No tactical data found in this sector."
            ctx["geojson"] = gdf.to_json()
            return gdf.drop(columns=["geom", "geometry"], errors="ignore").to_string()
        return f"SYSTEM_FAILURE: {error}"

    @tool
    def query_intel(request: str) -> str:
        """Search EXISTING intel already in the database: find, locate, list, count or
        analyze metro stations, parks, hospitals and infrastructure in Milan."""
        return _run_sql_pipeline(generate_query_sql, request, "query_intel")

    @tool
    def draw_geometry(request: str) -> str:
        """Synthesize a NEW geometry on the map (patrol zone, perimeter, area of
        operations, corridor, route, security buffer) from coordinates or a description.
        Does NOT read the database."""
        return _run_sql_pipeline(generate_geometry_sql, request, "draw_geometry")

    return [query_intel, draw_geometry]
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_tools.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat(agent): tool query_intel/draw_geometry con loop sicuro e self-correction"
```

---

## Task 8: Orchestrator (tool-calling + fallback router)

**Files:**
- Create: `agent/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `agent.prompts.AGENT_SYSTEM_PROMPT`; i tool prodotti da `make_tools`; `ConversationMemory`.
- Produces:
  - `keyword_router(message: str) -> str` → `"draw_geometry"` se il messaggio descrive una forma da disegnare, altrimenti `"query_intel"`.
  - `Orchestrator(*, llm, build_tools, analyze_image, briefing, memory, use_tools: bool, router)` con `run(message: str, session_id: str, image: bytes | None = None, mime_type: str = "image/jpeg") -> dict` → `{"text": str, "geojson": str | None}`.
    - `build_tools(ctx: dict) -> list` (factory che chiude su ctx); `analyze_image(image: bytes, context: str, mime_type: str) -> str`; `briefing(data_summary: str) -> str`.

- [ ] **Step 1: Scrivi i test orchestratore (devono fallire)**

Create `tests/test_orchestrator.py`:

```python
from agent.orchestrator import Orchestrator, keyword_router
from agent.memory import ConversationMemory


# --- keyword_router ---

def test_router_picks_draw_for_shape_verbs():
    assert keyword_router("draw a patrol perimeter around the duomo") == "draw_geometry"
    assert keyword_router("trace a route to Linate") == "draw_geometry"

def test_router_defaults_to_query():
    assert keyword_router("list all metro stations on M4") == "query_intel"


# --- fakes ---

class FakeTool:
    def __init__(self, name, ctx, geojson='{"gj":1}', text="ROWS"):
        self.name = name
        self._ctx = ctx
        self._geojson = geojson
        self._text = text
    def invoke(self, args):
        self._ctx["geojson"] = self._geojson
        return self._text

class FakeAI:
    def __init__(self, tool_calls=None, content=""):
        self.tool_calls = tool_calls or []
        self.content = content

class FakeBound:
    def __init__(self, ai):
        self._ai = ai
    def invoke(self, messages):
        return self._ai

class FakeLLM:
    def __init__(self, ai):
        self._ai = ai
    def bind_tools(self, tools):
        return FakeBound(self._ai)


def _orch(llm=None, use_tools=True, ctx_holder=None, briefing=None, analyze=None):
    def build_tools(ctx):
        if ctx_holder is not None:
            ctx_holder["ctx"] = ctx
        return [FakeTool("query_intel", ctx), FakeTool("draw_geometry", ctx)]
    return Orchestrator(
        llm=llm,
        build_tools=build_tools,
        analyze_image=analyze or (lambda image, context, mime_type: "RECON"),
        briefing=briefing or (lambda data: f"BRIEF[{data}]"),
        memory=ConversationMemory(),
        use_tools=use_tools,
        router=keyword_router,
    )


def test_image_path_bypasses_tools():
    orch = _orch(use_tools=True)
    out = orch.run("look here", "s1", image=b"IMG", mime_type="image/png")
    assert out["text"] == "RECON"
    assert out["geojson"] is None

def test_tool_calling_path_briefs_and_surfaces_geojson():
    ai = FakeAI(tool_calls=[{"name": "query_intel", "args": {"request": "metro"}}])
    orch = _orch(llm=FakeLLM(ai))
    out = orch.run("list metro", "s1")
    assert out["text"] == "BRIEF[ROWS]"
    assert out["geojson"] == '{"gj":1}'

def test_tool_calling_no_call_returns_model_content():
    ai = FakeAI(tool_calls=[], content="no actionable intel")
    orch = _orch(llm=FakeLLM(ai))
    out = orch.run("hello", "s1")
    assert out["text"] == "no actionable intel"
    assert out["geojson"] is None

def test_router_path_used_when_tools_disabled():
    orch = _orch(use_tools=False)
    out = orch.run("draw a perimeter", "s1")
    assert out["text"] == "BRIEF[ROWS]"
    assert out["geojson"] == '{"gj":1}'

def test_memory_is_recorded():
    ai = FakeAI(tool_calls=[{"name": "query_intel", "args": {"request": "metro"}}])
    mem = ConversationMemory()
    orch = Orchestrator(
        llm=FakeLLM(ai),
        build_tools=lambda ctx: [FakeTool("query_intel", ctx)],
        analyze_image=lambda image, context, mime_type: "RECON",
        briefing=lambda data: "BRIEF",
        memory=mem,
        use_tools=True,
        router=keyword_router,
    )
    orch.run("list metro", "s1")
    assert mem.get("s1") == [("user", "list metro"), ("assistant", "BRIEF")]
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.orchestrator'`.

- [ ] **Step 3: Implementa `agent/orchestrator.py`**

```python
import logging
import re

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .prompts import AGENT_SYSTEM_PROMPT

log = logging.getLogger(__name__)

_DRAW_HINTS = re.compile(
    r"\b(draw|create|mark|trace|define|perimeter|zone|corridor|route|buffer|"
    r"area of operations|radius)\b",
    re.IGNORECASE,
)


def keyword_router(message: str) -> str:
    """Fallback senza tool-calling nativo: sceglie il tool per parole chiave."""
    return "draw_geometry" if _DRAW_HINTS.search(message or "") else "query_intel"


class Orchestrator:
    def __init__(self, *, llm, build_tools, analyze_image, briefing, memory,
                 use_tools, router):
        self._llm = llm
        self._build_tools = build_tools
        self._analyze_image = analyze_image
        self._briefing = briefing
        self._memory = memory
        self._use_tools = use_tools
        self._router = router

    def run(self, message, session_id, image=None, mime_type="image/jpeg"):
        ctx = {"geojson": None}

        if image is not None:
            text = self._analyze_image(image, message or "", mime_type)
            self._record(session_id, message or "[IMAGE]", text)
            return {"text": text, "geojson": None}

        tools = self._build_tools(ctx)
        history = self._memory.get(session_id)

        if self._use_tools:
            text = self._run_tool_calling(message, history, tools)
        else:
            text = self._run_router(message, tools)

        self._record(session_id, message, text)
        return {"text": text, "geojson": ctx["geojson"]}

    # --- internals ---

    def _messages(self, history, message):
        msgs = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]
        for role, content in history:
            msgs.append(HumanMessage(content=content) if role == "user"
                        else AIMessage(content=content))
        msgs.append(HumanMessage(content=message))
        return msgs

    def _run_tool_calling(self, message, history, tools):
        registry = {t.name: t for t in tools}
        bound = self._llm.bind_tools(tools)
        ai = bound.invoke(self._messages(history, message))

        outputs = []
        for call in (getattr(ai, "tool_calls", None) or []):
            tool = registry.get(call["name"])
            if tool is None:
                continue
            outputs.append(tool.invoke(call["args"]))

        if not outputs:
            return ai.content or "No actionable intel."
        return self._briefing("\n".join(outputs))

    def _run_router(self, message, tools):
        registry = {t.name: t for t in tools}
        name = self._router(message)
        tool = registry.get(name) or registry["query_intel"]
        output = tool.invoke({"request": message})
        return self._briefing(output)

    def _record(self, session_id, user_msg, assistant_msg):
        self._memory.append(session_id, "user", user_msg)
        self._memory.append(session_id, "assistant", assistant_msg)
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(agent): orchestratore tool-calling + fallback router + memoria"
```

---

## Task 9: Wiring del package (`agent/__init__.py`)

**Files:**
- Modify: `agent/__init__.py`

**Interfaces:**
- Produces (API pubblica per `server.py`): `engine`, `vision_llm`, `config`, `analyze_satellite_image`, `run(message: str, session_id: str, image: bytes | None = None, mime_type: str = "image/jpeg") -> dict`.

- [ ] **Step 1: Implementa il wiring in `agent/__init__.py`**

```python
"""A.E.G.I.S. agent package: NL->PostGIS tool-calling con guardrail e memoria."""
import logging

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .config import load_config
from .db import make_engine, make_sql_database, get_table_info, execute_readonly
from .llm import build_text_llm, build_vision_llm
from .prompts import sql_query_template, GEOMETRY_TEMPLATE, BRIEFING_TEMPLATE
from .memory import ConversationMemory
from .tools import make_tools
from .vision import analyze_satellite_image
from .orchestrator import Orchestrator, keyword_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agent")

load_dotenv()
config = load_config()

text_llm = build_text_llm(config)
vision_llm = build_vision_llm(config)
memory = ConversationMemory(config.memory_turns)

# DB: degrada con grazia se offline (engine=None).
try:
    engine = make_engine(config.db_uri)
    _sql_db = make_sql_database(config.db_uri, config.schema)
    _table_info = get_table_info(_sql_db)
    log.info("DB connected. Schema: %s", config.schema)
except Exception as exc:  # noqa: BLE001
    log.error("DB init failed: %s", exc)
    engine = None
    _table_info = ""

_query_chain = (ChatPromptTemplate.from_template(sql_query_template(config.schema))
                | text_llm | StrOutputParser())
_geometry_chain = (ChatPromptTemplate.from_template(GEOMETRY_TEMPLATE)
                   | text_llm | StrOutputParser())
_briefing_chain = (ChatPromptTemplate.from_template(BRIEFING_TEMPLATE)
                   | text_llm | StrOutputParser())


def _generate_query_sql(request, error=""):
    return _query_chain.invoke({"table_info": _table_info, "question": request, "error": error})


def _generate_geometry_sql(request, error=""):
    return _geometry_chain.invoke({"request": request, "error": error})


def _execute_sql(sql):
    return execute_readonly(engine, sql, config.statement_timeout_ms)


def _briefing(data_summary):
    return _briefing_chain.invoke({"data_summary": data_summary})


def _analyze_image(image, context="", mime_type="image/jpeg"):
    return analyze_satellite_image(vision_llm, image, context, mime_type)


def _build_tools(ctx):
    return make_tools(
        generate_query_sql=_generate_query_sql,
        generate_geometry_sql=_generate_geometry_sql,
        execute_sql=_execute_sql,
        schema=config.schema,
        ctx=ctx,
    )


_orchestrator = Orchestrator(
    llm=text_llm,
    build_tools=_build_tools,
    analyze_image=_analyze_image,
    briefing=_briefing,
    memory=memory,
    use_tools=config.tool_calling,
    router=keyword_router,
)


def run(message, session_id, image=None, mime_type="image/jpeg"):
    if engine is None and image is None:
        return {"text": "Tactical engine offline.", "geojson": None}
    return _orchestrator.run(message, session_id, image, mime_type)


__all__ = ["engine", "vision_llm", "config", "run", "analyze_satellite_image"]
```

- [ ] **Step 2: Smoke test dell'import e suite completa**

Run: `python -c "import agent; print('ok', agent.config.schema)"`
Expected: stampa `ok schema1` (anche con DB/Ollama offline: l'import non deve sollevare).

Run: `python -m pytest tests/ -v`
Expected: PASS — l'intera suite verde.

- [ ] **Step 3: Commit**

```bash
git add agent/__init__.py
git commit -m "feat(agent): wiring del package e API pubblica run()/analyze"
```

---

## Task 10: Server sottile + session_id

**Files:**
- Modify: `server.py`

**Interfaces:**
- Consumes: `agent.run`, `agent.analyze_satellite_image`, `agent.vision_llm`, `agent.engine`.

- [ ] **Step 1: Aggiorna gli import e `ChatRequest`**

In `server.py` sostituisci la riga di import dell'agente:

```python
import agent
```

E aggiungi `session_id` al modello:

```python
class ChatRequest(BaseModel):
    message: str = ""
    image_data: str | None = None
    image_name: str | None = None
    session_id: str | None = None
```

- [ ] **Step 2: Riscrivi `/api/chat` sottile**

Sostituisci l'intero handler `chat_endpoint` con:

```python
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id or "anonymous"
    image_bytes = None
    mime_type = "image/jpeg"

    if request.image_data:
        try:
            image_bytes, mime_type = decode_image_payload(request.image_data)
        except Exception as e:
            print(f"Vision Error: {e}")
            raise HTTPException(status_code=400, detail="Invalid image payload.")

    try:
        return agent.run(
            message=request.message,
            session_id=session_id,
            image=image_bytes,
            mime_type=mime_type,
        )
    except Exception as e:
        print(f"Chat Error: {e}")
        return {"text": f"SYSTEM_FAILURE: {e}", "geojson": None}
```

- [ ] **Step 3: Allinea `/api/scan` al modello vision dedicato**

Nel handler `scan_endpoint`, sostituisci la riga di analisi:

```python
        description = agent.analyze_satellite_image(agent.vision_llm, buff.getvalue())
```

- [ ] **Step 4: Verifica che il server importi**

Run: `python -c "import server; print('server import ok')"`
Expected: stampa `server import ok` (con DB/Ollama offline l'import non deve sollevare).

- [ ] **Step 5: Commit**

```bash
git add server.py
git commit -m "refactor(server): endpoint sottili su agent.run + session_id"
```

---

## Task 11: Frontend — session_id end-to-end

**Files:**
- Modify: `js/script.js`

- [ ] **Step 1: Aggiungi l'helper `getSessionId`**

In `js/script.js`, subito dopo la riga `let pendingAttachment = null;` (≈ riga 60), inserisci:

```javascript
// --- SESSIONE: id stabile per la memoria conversazionale dell'agente ---
function getSessionId() {
    let id = localStorage.getItem('aegis_session_id');
    if (!id) {
        id = (window.crypto && crypto.randomUUID)
            ? crypto.randomUUID()
            : 'sess-' + Date.now() + '-' + Math.random().toString(16).slice(2);
        localStorage.setItem('aegis_session_id', id);
    }
    return id;
}
```

- [ ] **Step 2: Includi `session_id` nel payload di `/api/chat`**

Nel `sendMessage`, aggiorna il `payload` (≈ riga 172):

```javascript
        const payload = {
            message: message,
            image_data: pendingAttachment ? pendingAttachment.dataUrl : null,
            image_name: pendingAttachment ? pendingAttachment.name : null,
            session_id: getSessionId()
        };
```

- [ ] **Step 3: Verifica manuale rapida (browser)**

Apri `aegis.html`, esegui due richieste consecutive (es. *"list metro stations on M4"* poi *"now only show the ones near the center"*). Verifica in DevTools → Network che entrambe le `POST /api/chat` portino lo stesso `session_id`. (Richiede server + Ollama attivi; se non disponibili, salta e annota.)

- [ ] **Step 4: Commit**

```bash
git add js/script.js
git commit -m "feat(ui): invia session_id stabile per la memoria conversazionale"
```

---

## Task 12: Documentazione (.env + README)

**Files:**
- Modify: `.env`, `README.md`

- [ ] **Step 1: Documenta le nuove env var in `.env`**

Aggiungi in fondo alla sezione LLM di `.env`:

```bash
# --- Agent (opzionali) ---
# TEXT_MODEL e VISION_MODEL sovrascrivono MODEL_NAME per testo/vision separati.
# VISION_MODEL deve essere multimodale (es. llava, qwen3-vl). Fallback: MODEL_NAME.
# TEXT_MODEL=
# VISION_MODEL=llava
# STATEMENT_TIMEOUT_MS=5000   # timeout query DB
# MEMORY_TURNS=6              # turni di conversazione tenuti in memoria
# AGENT_TOOL_CALLING=on       # 'off' forza il router a parole chiave
```

- [ ] **Step 2: Aggiorna il README**

Nella sezione "Intelligence Layer" / "Getting Started" del `README.md`, sostituisci il riferimento a `agent.py` con il package `agent/` e aggiungi una riga sul setup:

In "Quick Start", aggiorna lo step dipendenze a:

```bash
pip install -r requirements.txt
```

E sostituisci lo step 2 ("Environment Setup ... in agent.py") con:

```markdown
2.  **Environment Setup**: Configura le credenziali nel file `.env` (vedi `.env`); l'agente è il package `agent/` (`agent.run`, `agent.analyze_satellite_image`).
```

- [ ] **Step 3: Esegui l'intera suite un'ultima volta**

Run: `python -m pytest tests/ -v`
Expected: PASS — tutta la suite verde.

- [ ] **Step 4: Commit**

```bash
git add .env README.md
git commit -m "docs: env var dell'agente e README allineato al package"
```

---

## Self-Review

**Spec coverage:**
- §3 Affidabilità SQL → Task 2 (extract/validate), Task 4 (few-shot prompts), Task 7 (loop self-correction). ✓
- §3/§7 Sicurezza doppio strato → Task 2 (validazione) + Task 5 (`execute_readonly` READ ONLY/timeout). ✓
- §3/§8 Memoria end-to-end → Task 3 (store) + Task 8 (record) + Task 10 (server) + Task 11 (frontend). ✓
- §3/§4 Qualità codice (package modulare) → Task 1–9. ✓
- §5 Tre tool → Task 7 (`query_intel`, `draw_geometry`) + Task 6/9 (`recon_image` come percorso immagine diretto nell'orchestratore, §6 step 2). ✓
- §6 Orchestratore + fallback → Task 8. ✓
- §9 Config coerente / modelli separati → Task 1 + Task 6. ✓
- §11 Logging → presente in db/tools/orchestrator/__init__. ✓
- §12 Test funzioni pure → Task 1–8 hanno test. ✓
- §10 Server sottile → Task 10. ✓

> **Nota di refinement vs spec:** nello spec `recon_image` era elencato come terzo tool legato al modello; in implementazione l'immagine non è trasportabile come argomento di tool-call, quindi l'orchestratore gestisce il percorso immagine **direttamente** (§6 step 2 dello spec). Comportamento equivalente; il modello lega solo `query_intel` e `draw_geometry`. Il fallback usa un router a parole chiave (`keyword_router`) anziché un classificatore LLM — più semplice e senza rete; eventuale upgrade futuro fuori scope.

**Placeholder scan:** nessun "TBD"/"TODO"/"handle edge cases" — ogni step ha codice o comando concreto. ✓

**Type consistency:** i tool espongono firma `(request: str)` ovunque (tools, orchestrator router, test); `ctx["geojson"]` usato in modo coerente tra `make_tools` e `Orchestrator`; `run(...)` ritorna sempre `{"text", "geojson"}`; `analyze_image(image, context, mime_type)` coerente tra vision/__init__/orchestrator. ✓
