# A.E.G.I.S. LangGraph Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrare l'orchestratore dell'agente a un `StateGraph` LangGraph multi-nodo con ragionamento multi-step (ReAct), analisi spaziale, chiarimento human-in-the-loop e grounding del briefing.

**Architecture:** Un `StateGraph` con stato `{messages, geojson, session_id}` e checkpointer `MemorySaver` (`thread_id=session_id`). Nodi `agent` (ReAct con `bind_tools`), `tools` (custom, senza `langgraph.prebuilt`), `clarify` (`interrupt()`), `ground`. L'agente imperativo esistente resta come fallback per modelli senza tool-calling.

**Tech Stack:** Python 3.12, LangGraph 1.0.6 (`StateGraph`, `MemorySaver`, `interrupt`, `Command`), LangChain 0.3 (`ChatOllama.bind_tools`), PostGIS, pytest.

## Global Constraints

- **NON usare `langgraph.prebuilt`** (`ToolNode`, `create_react_agent`): incompatibile col `langchain-core 0.3.63` installato (`ImportError: TOOL_MESSAGE_BLOCK_TYPES`). Tools node scritto a mano.
- **NON aggiornare** lo stack langchain (`langchain-core`/`langchain`/`langchain-community`/`langchain-ollama`): romperebbe l'agente e i 52 test verdi.
- **Sola lettura:** ogni tool SQL (incluso `spatial_analysis`) passa da `safety.validate_readonly_sql` + `db.execute_readonly` (transazione `READ ONLY`).
- **Schema:** sempre `Config.SCHEMA` iniettato nei prompt, mai `schema1` hardcoded.
- **Checkpointer:** `MemorySaver` in-memory; `thread_id = session_id`.
- **Determinismo:** `ChatOllama` di testo con `temperature=0`.
- **Branch:** `feature/agent-langgraph` (già creato).
- **Comando test:** dalla root → `python -m pytest tests/ -v`.
- **Nota file gitignored:** `requirements.txt` e `.env` sono in `.gitignore` → si aggiornano solo in locale (non committati). `langgraph` è già installato (1.0.6).

---

## File Structure

**Create:**
- `agent/geojson.py` — `merge_geojson(a, b)`.
- `agent/graph.py` — `AgentState`, `build_graph(...)`, nodi e routing.
- `tests/test_geojson.py`, `tests/test_graph.py`.

**Modify:**
- `agent/config.py` — campo `recursion_limit`.
- `agent/prompts.py` — `spatial_query_template()`, `GROUNDING_TEMPLATE`, `AGENT_SYSTEM_PROMPT` esteso.
- `agent/tools.py` — `run_sql_pipeline()`, `make_graph_tools()`, `request_clarification` (make_tools legacy invariato nel comportamento).
- `agent/__init__.py` — wiring del grafo + `run()` con `resume`/`awaiting_input` + dispatch fallback.
- `server.py` — `ChatRequest.resume`, passaggio a `agent.run`.
- `js/script.js` — gestione `awaiting_input`/`resume`.
- `tests/test_config.py`, `tests/test_prompts.py`, `tests/test_tools.py` — estesi.
- `README.md`, `.env` (locale) — nuova env `RECURSION_LIMIT`.

---

## Task 1: Config — recursion_limit + dipendenza langgraph

**Files:**
- Modify: `agent/config.py`, `requirements.txt` (locale), `tests/test_config.py`

**Interfaces:**
- Produces: `Config.recursion_limit: int` (default 12, da env `RECURSION_LIMIT`).

- [ ] **Step 1: Aggiungi `langgraph` a `requirements.txt`** (locale, gitignored)

Aggiungi la riga `langgraph` in fondo a `requirements.txt`. (Già installato; è solo documentazione della dipendenza.)

- [ ] **Step 2: Scrivi il test (deve fallire)**

Aggiungi in `tests/test_config.py`:

```python
def test_recursion_limit_default_and_override():
    assert load_config(BASE_ENV).recursion_limit == 12
    assert load_config({**BASE_ENV, "RECURSION_LIMIT": "5"}).recursion_limit == 5
```

- [ ] **Step 3: Esegui il test per verificare che fallisca**

Run: `python -m pytest tests/test_config.py::test_recursion_limit_default_and_override -v`
Expected: FAIL con `AttributeError: 'Config' object has no attribute 'recursion_limit'`.

- [ ] **Step 4: Implementa**

In `agent/config.py`, aggiungi il campo alla dataclass `Config` (dopo `tool_calling: bool`):

```python
    recursion_limit: int
```

E nella `return Config(...)` di `load_config`, aggiungi:

```python
        recursion_limit=int(env.get("RECURSION_LIMIT", "12")),
```

- [ ] **Step 5: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (8 passed).

- [ ] **Step 6: Commit**

```bash
git add agent/config.py tests/test_config.py
git commit -m "feat(agent): config.recursion_limit per il loop ReAct"
```

---

## Task 2: geojson.merge_geojson

**Files:**
- Create: `agent/geojson.py`
- Test: `tests/test_geojson.py`

**Interfaces:**
- Produces: `merge_geojson(a: str | None, b: str | None) -> str | None` — unisce due FeatureCollection GeoJSON (stringhe); tollera `None` e JSON non valido (ritorna il non-nullo).

- [ ] **Step 1: Scrivi i test (devono fallire)**

Create `tests/test_geojson.py`:

```python
import json
from agent.geojson import merge_geojson

FC_A = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"n":"A"},"geometry":null}]}'
FC_B = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"n":"B"},"geometry":null}]}'

def test_merge_none_cases():
    assert merge_geojson(None, None) is None
    assert merge_geojson(FC_A, None) == FC_A
    assert merge_geojson(None, FC_B) == FC_B

def test_merge_concatenates_features():
    merged = json.loads(merge_geojson(FC_A, FC_B))
    names = [f["properties"]["n"] for f in merged["features"]]
    assert names == ["A", "B"]
    assert merged["type"] == "FeatureCollection"

def test_merge_invalid_prefers_valid():
    assert merge_geojson("not-json", FC_B) == FC_B
    assert merge_geojson(FC_A, "not-json") == FC_A
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_geojson.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.geojson'`.

- [ ] **Step 3: Implementa `agent/geojson.py`**

```python
import json
from typing import Optional


def merge_geojson(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Unisce due FeatureCollection GeoJSON (stringhe). Tollera None e JSON invalido."""
    if a is None:
        return b
    if b is None:
        return a
    try:
        fa = json.loads(a)
        fb = json.loads(b)
    except (ValueError, TypeError):
        # Se uno dei due non è JSON valido, preferisci quello valido (a ha priorità).
        try:
            json.loads(a)
            return a
        except (ValueError, TypeError):
            return b
    features = (fa.get("features", []) or []) + (fb.get("features", []) or [])
    return json.dumps({"type": "FeatureCollection", "features": features})
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_geojson.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/geojson.py tests/test_geojson.py
git commit -m "feat(agent): merge_geojson per accumulo multi-step"
```

---

## Task 3: Prompts — spatial + grounding + system esteso

**Files:**
- Modify: `agent/prompts.py`, `tests/test_prompts.py`

**Interfaces:**
- Produces: `spatial_query_template(schema: str) -> str` (placeholder `{table_info}`,`{question}`,`{error}`); `GROUNDING_TEMPLATE: str` (placeholder `{draft}`,`{data}`); `AGENT_SYSTEM_PROMPT` menziona `spatial_analysis` e `request_clarification`.

- [ ] **Step 1: Scrivi i test (devono fallire)**

Aggiungi in `tests/test_prompts.py`:

```python
def test_spatial_template_injects_schema_and_placeholders():
    t = prompts.spatial_query_template("myschema")
    assert "myschema" in t
    assert "schema1" not in t
    for ph in ("{table_info}", "{question}", "{error}"):
        assert ph in t
    assert "ST_DWithin" in t or "ST_Distance" in t

def test_grounding_template_has_placeholders():
    assert "{draft}" in prompts.GROUNDING_TEMPLATE
    assert "{data}" in prompts.GROUNDING_TEMPLATE

def test_system_prompt_mentions_new_tools():
    p = prompts.AGENT_SYSTEM_PROMPT
    assert "spatial_analysis" in p
    assert "request_clarification" in p
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: FAIL (`AttributeError: module 'agent.prompts' has no attribute 'spatial_query_template'`).

- [ ] **Step 3: Implementa**

In `agent/prompts.py`, sostituisci `AGENT_SYSTEM_PROMPT` con la versione estesa:

```python
AGENT_SYSTEM_PROMPT = """\
IDENTITY: You are **Palantir**, the GEOINT engine of A.E.G.I.S., reporting to a field operator over a PostGIS database for the city of Milan.

You have tools. Choose and CHAIN them as needed to fulfil the request:
- `query_intel`   -> intel ALREADY in the database (find / locate / list / count metro stations, parks, hospitals, infrastructure).
- `spatial_analysis` -> DERIVED spatial questions: distance, nearest, within a radius, intersection (uses ST_Distance, ST_DWithin, ST_Intersects, KNN).
- `draw_geometry` -> DRAW / CREATE / MARK / TRACE a NEW shape on the map (zone, perimeter, corridor, route, buffer). Does NOT read the database.
- `request_clarification` -> when the request is ambiguous or missing required details (which line? which coordinates?). Call it ALONE and wait for the operator.

Multi-step is allowed: e.g. find hospitals, then draw a radius around each. When you have all the data, STOP calling tools and write a short, factual, tactical briefing based ONLY on the tool outputs. Never invent intel.

Every map result exposes a geometry column named `geom` in SRID 4326.
"""
```

Aggiungi in fondo al file `GROUNDING_TEMPLATE` e la funzione `spatial_query_template`:

```python
GROUNDING_TEMPLATE = """\
You are a strict fact-checker for a GEOINT briefing.
DATA returned by the tools:
{data}

DRAFT briefing:
{draft}

Rewrite the draft so that EVERY statement is supported by the DATA above.
Remove or correct any claim not present in the DATA. Keep it concise and tactical.
Return only the corrected briefing.
"""

_SPATIAL_QUERY_TEMPLATE = """\
### IDENTITY
You are **Palantir**, running DERIVED spatial analysis on a PostGIS PostgreSQL database for Milan.
Convert the operator's request into ONE valid, executable PostgreSQL/PostGIS SELECT.
Output the SQL only -- no prose, no markdown fences.

### HARD CONSTRAINTS
1. Emit ONE single SELECT statement.
2. The result MUST expose a geometry column named exactly `geom` in SRID 4326.
3. ALWAYS prefix tables with the schema name -> use {schema} (e.g. {schema}.hospitals).
4. Use spatial functions where relevant: ST_Distance, ST_DWithin, ST_Intersects, ST_Buffer, KNN `<->`.
5. Build point geometries as ST_SetSRID(ST_MakePoint(longitude, latitude), 4326). Cast to ::geography for metric distances.

### DATABASE SCHEMA
{table_info}

### EXAMPLES
- Hospitals within 1 km of the metro stop 'Duomo':
  SELECT h.name, ST_SetSRID(ST_MakePoint(h.longitude, h.latitude), 4326) AS geom
  FROM {schema}.hospitals h, {schema}.fermate_metro m
  WHERE m.name = 'Duomo'
    AND ST_DWithin(ST_SetSRID(ST_MakePoint(h.longitude, h.latitude),4326)::geography,
                   ST_SetSRID(ST_MakePoint(m.longitude, m.latitude),4326)::geography, 1000)
- Nearest metro stop to hospital 'Ospedale San Raffaele':
  SELECT m.name, ST_SetSRID(ST_MakePoint(m.longitude, m.latitude), 4326) AS geom
  FROM {schema}.fermate_metro m, {schema}.hospitals h
  WHERE h.name = 'Ospedale San Raffaele'
  ORDER BY ST_SetSRID(ST_MakePoint(m.longitude,m.latitude),4326) <-> ST_SetSRID(ST_MakePoint(h.longitude,h.latitude),4326)
  LIMIT 1

### ERROR CORRECTION
PREVIOUS ERROR: {error}
If the error is not empty, rewrite the query to fix the specific issue.

### REQUEST
{question}

### SQL
"""


def spatial_query_template(schema: str) -> str:
    """Template analisi spaziale con schema iniettato; liberi {table_info},{question},{error}."""
    return _SPATIAL_QUERY_TEMPLATE.replace("{schema}", schema)
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/prompts.py tests/test_prompts.py
git commit -m "feat(agent): prompt spatial_analysis + grounding + system esteso"
```

---

## Task 4: Tools — pipeline condivisa + make_graph_tools

**Files:**
- Modify: `agent/tools.py`, `tests/test_tools.py`

**Interfaces:**
- Produces:
  - `run_sql_pipeline(generate, request, *, execute_sql, schema, max_attempts=3) -> dict` con chiavi `{"summary": str, "geojson": str | None}`.
  - `make_graph_tools(*, generate_query_sql, generate_geometry_sql, generate_spatial_sql, execute_sql, schema, max_attempts=3) -> list` — tool `query_intel`, `draw_geometry`, `spatial_analysis`, ognuno `(request: str) -> dict`.
  - `make_tools(...)` legacy invariato nel comportamento (ctx + string) per il fallback.
- Consumes: `agent.safety.extract_sql`, `validate_readonly_sql`, `UnsafeQueryError`.

- [ ] **Step 1: Scrivi i test (devono fallire)**

Aggiungi in `tests/test_tools.py`:

```python
from agent.tools import run_sql_pipeline, make_graph_tools


def test_run_sql_pipeline_success_returns_dict():
    out = run_sql_pipeline(
        lambda request, error: "SELECT name FROM schema1.parks",
        "parks",
        execute_sql=lambda sql: FakeGDF(),
        schema="schema1",
    )
    assert "Duomo" in out["summary"]
    assert out["geojson"] is not None

def test_run_sql_pipeline_blocks_unsafe():
    calls = []
    out = run_sql_pipeline(
        lambda request, error: "DROP TABLE schema1.parks",
        "wipe",
        execute_sql=lambda sql: calls.append(sql) or FakeGDF(),
        schema="schema1",
    )
    assert "DENIED" in out["summary"]
    assert out["geojson"] is None
    assert calls == []

def test_make_graph_tools_names_and_dict_return():
    tools = {t.name: t for t in make_graph_tools(
        generate_query_sql=lambda request, error: "SELECT name FROM schema1.parks",
        generate_geometry_sql=lambda request, error: "SELECT 'L' AS label, 1 AS geom",
        generate_spatial_sql=lambda request, error: "SELECT name FROM schema1.hospitals",
        execute_sql=lambda sql: FakeGDF(),
        schema="schema1",
    )}
    assert set(tools) == {"query_intel", "draw_geometry", "spatial_analysis"}
    out = tools["spatial_analysis"].invoke({"request": "nearest"})
    assert out["geojson"] is not None
    assert "Duomo" in out["summary"]
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL (`ImportError: cannot import name 'run_sql_pipeline'`).

- [ ] **Step 3: Implementa (refactor + nuova factory)**

Sostituisci il contenuto di `agent/tools.py` con:

```python
import logging

from langchain_core.tools import tool

from .safety import extract_sql, validate_readonly_sql, UnsafeQueryError

log = logging.getLogger(__name__)


def run_sql_pipeline(generate, request, *, execute_sql, schema, max_attempts=3) -> dict:
    """genera->estrai->valida->esegui->auto-correggi. Ritorna {'summary','geojson'}."""
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
            log.warning("blocked unsafe SQL: %s", exc)
            return {"summary": f"REQUEST_DENIED: unsafe query blocked ({exc}).", "geojson": None}
        try:
            gdf = execute_sql(sql)
        except Exception as exc:  # noqa: BLE001 - errore re-immesso nell'LLM
            error = str(exc)
            log.warning("attempt %d failed: %s", attempt + 1, exc)
            continue
        if gdf.empty:
            return {"summary": "No tactical data found in this sector.", "geojson": None}
        return {
            "summary": gdf.drop(columns=["geom", "geometry"], errors="ignore").to_string(),
            "geojson": gdf.to_json(),
        }
    return {"summary": f"SYSTEM_FAILURE: {error}", "geojson": None}


def make_graph_tools(*, generate_query_sql, generate_geometry_sql, generate_spatial_sql,
                     execute_sql, schema, max_attempts=3):
    """Tool per il grafo LangGraph: ognuno ritorna {'summary','geojson'}."""

    @tool
    def query_intel(request: str) -> dict:
        """Search EXISTING intel already in the database: find, locate, list, count or
        analyze metro stations, parks, hospitals and infrastructure in Milan."""
        return run_sql_pipeline(generate_query_sql, request,
                                execute_sql=execute_sql, schema=schema, max_attempts=max_attempts)

    @tool
    def draw_geometry(request: str) -> dict:
        """Synthesize a NEW geometry on the map (patrol zone, perimeter, area of operations,
        corridor, route, security buffer) from coordinates or a description. Does NOT read the DB."""
        return run_sql_pipeline(generate_geometry_sql, request,
                                execute_sql=execute_sql, schema=schema, max_attempts=max_attempts)

    @tool
    def spatial_analysis(request: str) -> dict:
        """DERIVED spatial analysis over existing data: distance, nearest neighbour, within a
        radius, intersection (ST_Distance, ST_DWithin, ST_Intersects, KNN)."""
        return run_sql_pipeline(generate_spatial_sql, request,
                                execute_sql=execute_sql, schema=schema, max_attempts=max_attempts)

    return [query_intel, draw_geometry, spatial_analysis]


def make_tools(*, generate_query_sql, generate_geometry_sql, execute_sql,
               schema, ctx, max_attempts=3):
    """Legacy (fallback orchestrator): scrive il GeoJSON in ctx['geojson'] e ritorna una stringa."""

    def _body(generate, request):
        result = run_sql_pipeline(generate, request,
                                  execute_sql=execute_sql, schema=schema, max_attempts=max_attempts)
        if result["geojson"] is not None:
            ctx["geojson"] = result["geojson"]
        return result["summary"]

    @tool
    def query_intel(request: str) -> str:
        """Search EXISTING intel already in the database: find, locate, list, count or
        analyze metro stations, parks, hospitals and infrastructure in Milan."""
        return _body(generate_query_sql, request)

    @tool
    def draw_geometry(request: str) -> str:
        """Synthesize a NEW geometry on the map (patrol zone, perimeter, area of operations,
        corridor, route, security buffer) from coordinates or a description. Does NOT read the DB."""
        return _body(generate_geometry_sql, request)

    return [query_intel, draw_geometry]
```

- [ ] **Step 4: Esegui i test (devono passare — inclusi i vecchi test_tools)**

Run: `python -m pytest tests/test_tools.py -v`
Expected: PASS (i 5 test legacy + i 3 nuovi).

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat(agent): pipeline SQL condivisa + make_graph_tools (dict return)"
```

---

## Task 5: Graph — agent/tools/ground + multi-step

**Files:**
- Create: `agent/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Produces: `AgentState` (TypedDict: `messages: Annotated[list, add_messages]`, `geojson: Annotated[Optional[str], merge_geojson]`, `session_id: str`); `build_graph(*, llm, tools, ground_fn, checkpointer) -> CompiledGraph`.
  - `llm`: oggetto con `.bind_tools(tools) -> obj` con `.invoke(messages) -> AIMessage`.
  - `tools`: lista di tool `(request:str)->dict{"summary","geojson"}`.
  - `ground_fn(draft: str, data: str) -> str`.

- [ ] **Step 1: Scrivi i test (devono fallire)**

Create `tests/test_graph.py`:

```python
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph


FC1 = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"n":1},"geometry":null}]}'


@tool
def fake_query(request: str) -> dict:
    """query existing intel"""
    return {"summary": "ROWS: Duomo", "geojson": FC1}


class ScriptedLLM:
    """Ritorna in sequenza gli AIMessage predefiniti a ogni invoke."""
    def __init__(self, scripted):
        self._scripted = scripted
        self._i = 0
    def bind_tools(self, tools):
        return self
    def invoke(self, messages):
        ai = self._scripted[self._i]
        self._i += 1
        return ai


def _cfg(tid="t1"):
    return {"configurable": {"thread_id": tid}, "recursion_limit": 12}


def test_multi_step_then_final_and_geojson():
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "fake_query", "args": {"request": "metro"}, "id": "c1"}]),
        AIMessage(content="draft briefing"),  # nessun tool_call -> ground -> END
    ]
    graph = build_graph(llm=ScriptedLLM(scripted), tools=[fake_query],
                        ground_fn=lambda draft, data: draft.upper(), checkpointer=MemorySaver())
    out = graph.invoke({"messages": [("user", "list metro")], "geojson": None, "session_id": "t1"}, _cfg())
    assert out["messages"][-1].content == "DRAFT BRIEFING"   # grounding applicato
    assert out["geojson"] == FC1

def test_grounding_receives_tool_data():
    seen = {}
    def ground(draft, data):
        seen["data"] = data
        return draft
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "fake_query", "args": {"request": "x"}, "id": "c1"}]),
        AIMessage(content="final"),
    ]
    graph = build_graph(llm=ScriptedLLM(scripted), tools=[fake_query],
                        ground_fn=ground, checkpointer=MemorySaver())
    graph.invoke({"messages": [("user", "q")], "geojson": None, "session_id": "t2"}, _cfg("t2"))
    assert "Duomo" in seen["data"]
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_graph.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'agent.graph'`).

- [ ] **Step 3: Implementa `agent/graph.py`**

```python
from typing import TypedDict, Annotated, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage

from .prompts import AGENT_SYSTEM_PROMPT
from .geojson import merge_geojson


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    geojson: Annotated[Optional[str], merge_geojson]
    session_id: str


def build_graph(*, llm, tools, ground_fn, checkpointer):
    registry = {t.name: t for t in tools}

    def agent_node(state: AgentState):
        bound = llm.bind_tools(tools)
        ai = bound.invoke([SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state["messages"])
        return {"messages": [ai]}

    def tools_node(state: AgentState):
        last = state["messages"][-1]
        tool_messages = []
        geo = None
        for call in last.tool_calls:
            tool = registry.get(call["name"])
            if tool is None:
                tool_messages.append(ToolMessage(content=f"unknown tool {call['name']}",
                                                 tool_call_id=call["id"]))
                continue
            result = tool.invoke(call["args"])
            tool_messages.append(ToolMessage(content=result["summary"], tool_call_id=call["id"]))
            geo = merge_geojson(geo, result.get("geojson"))
        return {"messages": tool_messages, "geojson": geo}

    def ground_node(state: AgentState):
        last = state["messages"][-1]
        data = "\n".join(m.content for m in state["messages"] if isinstance(m, ToolMessage))
        grounded = ground_fn(last.content, data)
        return {"messages": [AIMessage(content=grounded, id=last.id)]}

    def route_after_agent(state: AgentState):
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "ground"

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("ground", ground_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "ground": "ground"})
    g.add_edge("tools", "agent")
    g.add_edge("ground", END)
    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_graph.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/graph.py tests/test_graph.py
git commit -m "feat(agent): StateGraph ReAct (agent/tools/ground) + accumulo geojson"
```

---

## Task 6: Graph — clarify (human-in-the-loop)

**Files:**
- Modify: `agent/graph.py`, `agent/tools.py`, `tests/test_graph.py`

**Interfaces:**
- Produces: `agent.tools.request_clarification` (`@tool (question:str)->dict`); `build_graph` gestisce il nodo `clarify` (via `interrupt`) quando l'AI chiama `request_clarification`.

- [ ] **Step 1: Scrivi il test (deve fallire)**

Aggiungi in `tests/test_graph.py`:

```python
from langgraph.types import Command
from agent.tools import request_clarification


def test_clarify_interrupts_then_resumes():
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "request_clarification",
                                           "args": {"question": "Quale linea?"}, "id": "c1"}]),
        AIMessage(content="done"),  # dopo il resume, nessun tool -> ground -> END
    ]
    graph = build_graph(llm=ScriptedLLM(scripted), tools=[fake_query, request_clarification],
                        ground_fn=lambda draft, data: draft, checkpointer=MemorySaver())
    cfg = _cfg("t3")
    res = graph.invoke({"messages": [("user", "metro")], "geojson": None, "session_id": "t3"}, cfg)
    assert res["__interrupt__"][0].value["question"] == "Quale linea?"
    res2 = graph.invoke(Command(resume="M4"), cfg)
    assert res2["messages"][-1].content == "done"
```

- [ ] **Step 2: Esegui il test per verificare che fallisca**

Run: `python -m pytest tests/test_graph.py::test_clarify_interrupts_then_resumes -v`
Expected: FAIL (`ImportError: cannot import name 'request_clarification'`).

- [ ] **Step 3: Implementa**

In `agent/tools.py`, aggiungi in cima (dopo gli import) il tool sentinella:

```python
@tool
def request_clarification(question: str) -> dict:
    """Ask the operator ONE clarifying question when the request is ambiguous or missing
    required details (which metro line? which coordinates?). Call this ALONE."""
    return {"summary": question, "geojson": None}
```

In `agent/graph.py`, aggiorna gli import e aggiungi il nodo `clarify`:

```python
from langgraph.types import interrupt
```

Aggiungi la costante in cima al modulo:

```python
CLARIFY_TOOL_NAME = "request_clarification"
```

Dentro `build_graph`, aggiungi il nodo `clarify_node` e modifica il routing:

```python
    def clarify_node(state: AgentState):
        last = state["messages"][-1]
        question = next((c["args"].get("question", "Chiarimento richiesto.")
                         for c in last.tool_calls if c["name"] == CLARIFY_TOOL_NAME),
                        "Chiarimento richiesto.")
        answer = interrupt({"question": question})
        msgs = []
        for c in last.tool_calls:
            content = answer if c["name"] == CLARIFY_TOOL_NAME else "(in attesa di chiarimento)"
            msgs.append(ToolMessage(content=content, tool_call_id=c["id"]))
        return {"messages": msgs}
```

Sostituisci `route_after_agent` con:

```python
    def route_after_agent(state: AgentState):
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None)
        if not calls:
            return "ground"
        if any(c["name"] == CLARIFY_TOOL_NAME for c in calls):
            return "clarify"
        return "tools"
```

E registra nodo/archi (prima di `compile`):

```python
    g.add_node("clarify", clarify_node)
    g.add_conditional_edges("agent", route_after_agent,
                            {"tools": "tools", "ground": "ground", "clarify": "clarify"})
    g.add_edge("clarify", "agent")
```

> Nota: rimuovi la vecchia `g.add_conditional_edges("agent", route_after_agent, {"tools": ..., "ground": ...})` del Task 5 e tienine una sola con i tre rami.

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_graph.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/graph.py agent/tools.py tests/test_graph.py
git commit -m "feat(agent): nodo clarify human-in-the-loop via interrupt"
```

---

## Task 7: Wiring — grafo compilato + run() con resume

**Files:**
- Modify: `agent/__init__.py`

**Interfaces:**
- Produces: `run(message, session_id, image=None, mime_type="image/jpeg", resume=None) -> dict` con `{"text", "geojson", "awaiting_input"}`.

- [ ] **Step 1: Estendi il wiring in `agent/__init__.py`**

Aggiorna gli import (in cima, insieme agli altri `from .`):

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage

from .prompts import spatial_query_template, GROUNDING_TEMPLATE
from .tools import make_graph_tools, request_clarification
from .graph import build_graph
```

Dopo la definizione di `_briefing`/`_analyze_image`/`_build_tools` esistenti, aggiungi:

```python
_spatial_chain = (ChatPromptTemplate.from_template(spatial_query_template(config.schema))
                  | text_llm | StrOutputParser())
_grounding_chain = (ChatPromptTemplate.from_template(GROUNDING_TEMPLATE)
                    | text_llm | StrOutputParser())


def _generate_spatial_sql(request, error=""):
    return _spatial_chain.invoke({"table_info": _table_info, "question": request, "error": error})


def _ground(draft, data):
    if not data.strip():
        return draft
    return _grounding_chain.invoke({"draft": draft, "data": data})


_graph_tools = make_graph_tools(
    generate_query_sql=_generate_query_sql,
    generate_geometry_sql=_generate_geometry_sql,
    generate_spatial_sql=_generate_spatial_sql,
    execute_sql=_execute_sql,
    schema=config.schema,
) + [request_clarification]

_graph = build_graph(llm=text_llm, tools=_graph_tools, ground_fn=_ground,
                     checkpointer=MemorySaver())
```

Sostituisci la funzione `run(...)` esistente con:

```python
def run(message, session_id, image=None, mime_type="image/jpeg", resume=None):
    # Fallback per modelli senza tool-calling nativo.
    if not config.tool_calling:
        out = _orchestrator.run(message, session_id, image, mime_type)
        return {**out, "awaiting_input": False}

    if engine is None and image is None:
        return {"text": "Tactical engine offline.", "geojson": None, "awaiting_input": False}

    cfg = {"configurable": {"thread_id": session_id}, "recursion_limit": config.recursion_limit}

    if image is not None:
        text = _analyze_image(image, message or "", mime_type)
        return {"text": text, "geojson": None, "awaiting_input": False}

    if resume is not None:
        inp = Command(resume=resume)
    else:
        inp = {"messages": [HumanMessage(content=message)], "session_id": session_id, "geojson": None}

    result = _graph.invoke(inp, cfg)

    if result.get("__interrupt__"):
        question = result["__interrupt__"][0].value.get("question", "Chiarimento richiesto.")
        return {"text": question, "geojson": None, "awaiting_input": True}

    final = result["messages"][-1].content
    return {"text": final, "geojson": result.get("geojson"), "awaiting_input": False}
```

Aggiorna `__all__` per includere l'invariato set pubblico (nessuna nuova voce necessaria: `run` è già esportato).

- [ ] **Step 2: Smoke test import + suite**

Run: `python -c "import agent; print('ok', bool(agent._graph))"`
Expected: stampa `ok True` (import non solleva anche con Ollama offline).

Run: `python -m pytest tests/ -q`
Expected: PASS — intera suite verde.

- [ ] **Step 3: Commit**

```bash
git add agent/__init__.py
git commit -m "feat(agent): wiring StateGraph + run() con resume/awaiting_input"
```

---

## Task 8: Server — resume + awaiting_input

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Aggiungi `resume` a `ChatRequest`**

```python
class ChatRequest(BaseModel):
    message: str = ""
    image_data: str | None = None
    image_name: str | None = None
    session_id: str | None = None
    resume: str | None = None
```

- [ ] **Step 2: Passa `resume` in `/api/chat`**

Nel corpo di `chat_endpoint`, sostituisci la chiamata `agent.run(...)` con:

```python
    try:
        return agent.run(
            message=request.message,
            session_id=session_id,
            image=image_bytes,
            mime_type=mime_type,
            resume=request.resume,
        )
    except Exception as e:
        print(f"Chat Error: {e}")
        return {"text": f"SYSTEM_FAILURE: {e}", "geojson": None, "awaiting_input": False}
```

- [ ] **Step 3: Verifica import server**

Run: `python -c "import server; print('server import ok')"`
Expected: stampa `server import ok`.

- [ ] **Step 4: Commit**

```bash
git add server.py
git commit -m "feat(server): supporto resume + awaiting_input per human-in-the-loop"
```

---

## Task 9: Frontend — awaiting_input / resume

**Files:**
- Modify: `js/script.js`

- [ ] **Step 1: Aggiungi lo stato di attesa chiarimento**

Subito dopo `function getSessionId() { ... }` (che hai aggiunto in precedenza), inserisci:

```javascript
// --- Stato human-in-the-loop: true quando l'agente attende un chiarimento ---
let awaitingClarification = false;
```

- [ ] **Step 2: Invia `resume` quando in attesa e leggi `awaiting_input`**

Nel `sendMessage`, sostituisci la costruzione del `payload` con:

```javascript
        const payload = {
            message: awaitingClarification ? '' : message,
            image_data: pendingAttachment ? pendingAttachment.dataUrl : null,
            image_name: pendingAttachment ? pendingAttachment.name : null,
            session_id: getSessionId(),
            resume: awaitingClarification ? message : null
        };
```

E dopo aver ricevuto e mostrato la risposta AI (`addMessage(data.text, 'ai');`), aggiorna il flag:

```javascript
        awaitingClarification = Boolean(data.awaiting_input);
```

- [ ] **Step 3: Verifica manuale (browser)**

Apri `aegis.html` con server + Ollama attivi. Invia una richiesta ambigua (es. *"mostra le fermate"* senza specificare la linea). Se l'agente chiede un chiarimento, la risposta successiva deve arrivare come `resume` (stesso `session_id`) e completare il turno. (Se Ollama/DB non disponibili, salta e annota.)

- [ ] **Step 4: Commit**

> Nota: `js/script.js` contiene WIP dell'utente. Committa solo se l'utente lo richiede; altrimenti lascia la modifica applicata e non committata (come per il `session_id`).

---

## Task 10: Documentazione

**Files:**
- Modify: `README.md`, `.env` (locale, gitignored)

- [ ] **Step 1: Documenta `RECURSION_LIMIT` in `.env`**

Aggiungi nella sezione "Agent (opzionali)" di `.env`:

```bash
# RECURSION_LIMIT=12          # max passi ReAct per turno del grafo LangGraph
```

- [ ] **Step 2: Aggiorna il README**

Nella sezione "Intelligence Layer" del `README.md`, aggiungi una riga:

```markdown
* **LangGraph Agent**: l'orchestrazione è un `StateGraph` (nodi `agent`/`tools`/`clarify`/`ground`) con ragionamento multi-step (ReAct), analisi spaziale (`spatial_analysis`), chiarimento human-in-the-loop (`interrupt`) e grounding del briefing. Checkpointer in-memory per `session_id`.
```

- [ ] **Step 3: Suite completa finale**

Run: `python -m pytest tests/ -q`
Expected: PASS — tutta la suite verde.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README allineato all'agente LangGraph"
```

---

## Self-Review

**Spec coverage:**
- §1/§3 StateGraph + stato + checkpointer → Task 5 (build_graph) + Task 7 (MemorySaver, thread_id). ✓
- §1 multi-step ReAct → Task 5 (loop agent↔tools). ✓
- §1/§4 spatial_analysis → Task 3 (prompt) + Task 4 (tool) + Task 7 (generator). ✓
- §1/§3 clarify human-in-the-loop → Task 6 (interrupt) + Task 7/8/9 (resume end-to-end). ✓
- §1/§3 ground → Task 5 (ground node) + Task 3 (GROUNDING_TEMPLATE) + Task 7 (_ground). ✓
- §2 niente langgraph.prebuilt → tools_node custom in Task 5. ✓
- §5 guardrail read-only → Task 4 (run_sql_pipeline usa safety) + db.execute_readonly riusato. ✓
- §6 contratto awaiting_input/resume → Task 7/8/9. ✓
- §7 fallback orchestrator quando tool_calling off → Task 7 (dispatch). ✓
- §3 accumulo geojson → Task 2 (merge_geojson) + Task 5 (reducer + tools_node). ✓
- §8 test → Task 2/3/4/5/6 con test; suite esistente preservata. ✓

**Placeholder scan:** nessun TBD/TODO; ogni step ha codice o comando concreto. Le note su `js/script.js` non committato e su file gitignored sono intenzionali, non placeholder. ✓

**Type consistency:** i tool del grafo ritornano sempre `dict{"summary","geojson"}` (Task 4/5/6); `run_sql_pipeline` firma coerente ovunque; `build_graph(*, llm, tools, ground_fn, checkpointer)` invariata tra Task 5 e 7; `run(...)` ritorna sempre `{"text","geojson","awaiting_input"}` (Task 7/8); `merge_geojson(a,b)` usata sia come reducer sia nel tools_node. ✓

> **Refinement vs spec:** la spec (§7) diceva "make_tools riadattato"; in implementazione si aggiunge `make_graph_tools` (dict) e si lascia `make_tools` legacy invariato per il fallback, condividendo `run_sql_pipeline`. Nessun test verde viene rotto. Equivalente funzionalmente.
