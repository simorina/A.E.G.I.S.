# A.E.G.I.S. Conversations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conversazioni persistenti e organizzate per operatore: sidebar con nuova chat, elenco, apertura, rinomina ed eliminazione; memoria dell'agente che sopravvive al riavvio.

**Architecture:** Due tabelle applicative (`schema1.conversations`, `schema1.messages`) gestite da un modulo `agent/conversations.py` con SQL parametrizzato; endpoint REST in `server.py`; checkpointer LangGraph su Postgres con fallback a `MemorySaver`; UI nella sidebar esistente.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (engine esistente), PostgreSQL/PostGIS, LangGraph, JS vanilla + Leaflet.

## Global Constraints

- **Schema:** tutte le tabelle in `Config.SCHEMA` (`schema1`); mai hardcodare `schema1` nel codice Python — usare `config.schema` (accettabile in `db/init.sql`, che è già schema-specifico).
- **SQL parametrizzato sempre** (`text()` + parametri bind). Nessuna interpolazione di stringhe nei valori.
- **`thread_id` del grafo = `conversation_id`**; `session_id` resta accettato da `/api/chat` per compatibilità (fallback se `conversation_id` è assente).
- **DB offline:** gli endpoint conversazioni rispondono **503**; `/api/chat` continua a funzionare senza persistenza (non regredire il comportamento "tool geo attivi col DB spento"). Il checkpointer degrada a `MemorySaver`.
- **`DEFAULT_TITLE = "NUOVA CONVERSAZIONE"`**; il titolo automatico si applica solo se il titolo corrente è ancora quello.
- **Nessun `git add -A`**: stage solo i file elencati nel task (il working tree può contenere WIP dell'utente).
- **Trailer di ogni commit:** `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **Comando test:** dalla root → `python -m pytest tests/ -q`.
- **Branch:** `feature/conversations` (già creato).
- **`requirements.txt` è gitignored:** le nuove dipendenze si installano/annotano in locale, non compaiono nei commit.

---

## File Structure

**Create:**
- `agent/conversations.py` — CRUD conversazioni/messaggi + `derive_title` (unica responsabilità: persistenza chat).
- `tests/test_conversations.py` — test di `derive_title` (puri) e CRUD (skip se DB assente).
- `tests/test_checkpointer.py` — test del selettore di checkpointer.

**Modify:**
- `db/init.sql` — DDL delle due tabelle (per DB nuovi).
- `agent/__init__.py` — `ensure_schema()` all'avvio, selettore checkpointer, `run(..., conversation_id)`.
- `server.py` — 5 endpoint conversazioni + `conversation_id` in `/api/chat` + salvataggio messaggi.
- `index.html` — salva `operator_id` in `sessionStorage` al login.
- `aegis.html` — blocco sidebar (nuova chat + lista).
- `js/script.js` — stato conversazione, fetch API, rendering lista, apertura/rinomina/elimina.
- `css/style.css` — stile della lista conversazioni.
- `arch.md` — sezione conversazioni.

---

## Task 1: Modulo conversations (derive_title + CRUD)

**Files:**
- Create: `agent/conversations.py`, `tests/test_conversations.py`
- Modify: `db/init.sql`

**Interfaces:**
- Produces:
  - `DEFAULT_TITLE: str = "NUOVA CONVERSAZIONE"`
  - `derive_title(text: str, max_len: int = 40) -> str`
  - `ensure_schema(engine, schema: str) -> None`
  - `create_conversation(engine, schema: str, operator_id: str, title: str = DEFAULT_TITLE) -> dict` → `{"id","operator_id","title","created_at","updated_at"}` (datetime in ISO string)
  - `list_conversations(engine, schema: str, operator_id: str) -> list[dict]`
  - `get_conversation(engine, schema: str, conversation_id: str) -> dict | None`
  - `get_messages(engine, schema: str, conversation_id: str) -> list[dict]` → `[{"role","content","geojson","created_at"}]`
  - `append_message(engine, schema: str, conversation_id: str, role: str, content: str, geojson: str | None = None) -> None`
  - `rename_conversation(engine, schema: str, conversation_id: str, title: str) -> bool`
  - `delete_conversation(engine, schema: str, conversation_id: str) -> bool`

- [ ] **Step 1: Scrivi i test di `derive_title` (devono fallire)**

Create `tests/test_conversations.py`:

```python
import pytest

from agent.conversations import DEFAULT_TITLE, derive_title


def test_derive_title_uses_first_line():
    assert derive_title("traccia via dante\nseconda riga") == "traccia via dante"


def test_derive_title_truncates_with_ellipsis():
    long = "traccia tutte le vie principali del centro storico di milano"
    out = derive_title(long, max_len=20)
    assert len(out) <= 21          # 20 caratteri + ellissi
    assert out.endswith("…")


def test_derive_title_normalises_whitespace():
    assert derive_title("   traccia    via   dante   ") == "traccia via dante"


def test_derive_title_empty_falls_back_to_default():
    assert derive_title("") == DEFAULT_TITLE
    assert derive_title("   \n  ") == DEFAULT_TITLE
```

- [ ] **Step 2: Esegui i test per verificare che falliscano**

Run: `python -m pytest tests/test_conversations.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.conversations'`.

- [ ] **Step 3: Implementa `agent/conversations.py`**

```python
import logging
import uuid

from sqlalchemy import text

log = logging.getLogger(__name__)

DEFAULT_TITLE = "NUOVA CONVERSAZIONE"


def derive_title(text_value: str, max_len: int = 40) -> str:
    """Titolo dalla prima riga del messaggio, normalizzata e troncata."""
    first_line = (text_value or "").strip().splitlines()[0] if (text_value or "").strip() else ""
    cleaned = " ".join(first_line.split())
    if not cleaned:
        return DEFAULT_TITLE
    if len(cleaned) > max_len:
        return cleaned[:max_len] + "…"
    return cleaned


def ensure_schema(engine, schema: str) -> None:
    """Crea le tabelle applicative se assenti (idempotente)."""
    ddl = [
        f"""CREATE TABLE IF NOT EXISTS {schema}.conversations (
                id          UUID PRIMARY KEY,
                operator_id VARCHAR(64)  NOT NULL,
                title       VARCHAR(120) NOT NULL,
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now())""",
        f"""CREATE INDEX IF NOT EXISTS conversations_operator_idx
                ON {schema}.conversations (operator_id, updated_at DESC)""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.messages (
                id              BIGSERIAL PRIMARY KEY,
                conversation_id UUID NOT NULL
                    REFERENCES {schema}.conversations(id) ON DELETE CASCADE,
                role            VARCHAR(16) NOT NULL,
                content         TEXT NOT NULL,
                geojson         TEXT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now())""",
        f"""CREATE INDEX IF NOT EXISTS messages_conversation_idx
                ON {schema}.messages (conversation_id, id)""",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))


def _row_to_conversation(row) -> dict:
    return {
        "id": str(row.id),
        "operator_id": row.operator_id,
        "title": row.title,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def create_conversation(engine, schema: str, operator_id: str, title: str = DEFAULT_TITLE) -> dict:
    new_id = str(uuid.uuid4())
    with engine.begin() as conn:
        row = conn.execute(text(
            f"""INSERT INTO {schema}.conversations (id, operator_id, title)
                VALUES (:id, :operator_id, :title)
                RETURNING id, operator_id, title, created_at, updated_at"""),
            {"id": new_id, "operator_id": operator_id, "title": title}).one()
        return _row_to_conversation(row)


def list_conversations(engine, schema: str, operator_id: str) -> list:
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"""SELECT id, operator_id, title, created_at, updated_at
                FROM {schema}.conversations
                WHERE operator_id = :operator_id
                ORDER BY updated_at DESC"""),
            {"operator_id": operator_id}).all()
    return [_row_to_conversation(r) for r in rows]


def get_conversation(engine, schema: str, conversation_id: str):
    with engine.connect() as conn:
        row = conn.execute(text(
            f"""SELECT id, operator_id, title, created_at, updated_at
                FROM {schema}.conversations WHERE id = :id"""),
            {"id": conversation_id}).first()
    return _row_to_conversation(row) if row else None


def get_messages(engine, schema: str, conversation_id: str) -> list:
    with engine.connect() as conn:
        rows = conn.execute(text(
            f"""SELECT role, content, geojson, created_at
                FROM {schema}.messages
                WHERE conversation_id = :cid ORDER BY id"""),
            {"cid": conversation_id}).all()
    return [{"role": r.role, "content": r.content, "geojson": r.geojson,
             "created_at": r.created_at.isoformat()} for r in rows]


def append_message(engine, schema: str, conversation_id: str, role: str,
                   content: str, geojson=None) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            f"""INSERT INTO {schema}.messages (conversation_id, role, content, geojson)
                VALUES (:cid, :role, :content, :geojson)"""),
            {"cid": conversation_id, "role": role, "content": content, "geojson": geojson})
        conn.execute(text(
            f"UPDATE {schema}.conversations SET updated_at = now() WHERE id = :cid"),
            {"cid": conversation_id})


def rename_conversation(engine, schema: str, conversation_id: str, title: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(text(
            f"UPDATE {schema}.conversations SET title = :title, updated_at = now() WHERE id = :cid"),
            {"title": title, "cid": conversation_id})
    return result.rowcount > 0


def delete_conversation(engine, schema: str, conversation_id: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(text(
            f"DELETE FROM {schema}.conversations WHERE id = :cid"), {"cid": conversation_id})
    return result.rowcount > 0
```

- [ ] **Step 4: Esegui i test (devono passare)**

Run: `python -m pytest tests/test_conversations.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Aggiungi i test CRUD (skip senza DB)**

Aggiungi in fondo a `tests/test_conversations.py`:

```python
@pytest.fixture(scope="module")
def db():
    """Engine reale se il DB è raggiungibile, altrimenti skip dei test CRUD."""
    import agent
    from agent.conversations import ensure_schema
    if agent.engine is None:
        pytest.skip("DB non raggiungibile: test CRUD saltati")
    ensure_schema(agent.engine, agent.config.schema)
    return agent.engine, agent.config.schema


def test_crud_roundtrip(db):
    from agent.conversations import (create_conversation, list_conversations, get_messages,
                                     append_message, rename_conversation, delete_conversation)
    engine, schema = db
    conv = create_conversation(engine, schema, "TEST_OP")
    assert conv["title"] == DEFAULT_TITLE

    append_message(engine, schema, conv["id"], "user", "ciao")
    append_message(engine, schema, conv["id"], "assistant", "briefing", geojson='{"a":1}')
    msgs = get_messages(engine, schema, conv["id"])
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["geojson"] == '{"a":1}'

    assert rename_conversation(engine, schema, conv["id"], "MISSIONE ALFA") is True
    titles = {c["id"]: c["title"] for c in list_conversations(engine, schema, "TEST_OP")}
    assert titles[conv["id"]] == "MISSIONE ALFA"

    assert delete_conversation(engine, schema, conv["id"]) is True
    assert conv["id"] not in {c["id"] for c in list_conversations(engine, schema, "TEST_OP")}
    assert get_messages(engine, schema, conv["id"]) == []   # cascade
```

- [ ] **Step 6: Esegui i test**

Run: `python -m pytest tests/test_conversations.py -q`
Expected: PASS (5 passed) se il DB è attivo; PASS con 1 skipped se è spento. Entrambi gli esiti sono accettabili.

- [ ] **Step 7: Aggiungi il DDL a `db/init.sql`**

Aggiungi in fondo a `db/init.sql`, prima del blocco `DO $$ ... sanity`:

```sql
-- ---------------------------------------------------------------------
-- CONVERSATIONS / MESSAGES  (chat salvate per operatore)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema1.conversations (
    id          UUID PRIMARY KEY,
    operator_id VARCHAR(64)  NOT NULL,
    title       VARCHAR(120) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS conversations_operator_idx
    ON schema1.conversations (operator_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS schema1.messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES schema1.conversations(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,
    content         TEXT NOT NULL,
    geojson         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_conversation_idx
    ON schema1.messages (conversation_id, id);
```

- [ ] **Step 8: Commit**

```bash
git add agent/conversations.py tests/test_conversations.py db/init.sql
git commit -m "feat(agent): modulo conversations (CRUD chat + derive_title)"
```

---

## Task 2: Checkpointer persistente con fallback

**Files:**
- Create: `tests/test_checkpointer.py`
- Modify: `agent/__init__.py`

**Interfaces:**
- Consumes: `agent.conversations.ensure_schema`.
- Produces: `agent.build_checkpointer(db_uri: str | None) -> (checkpointer, kind: str)` dove `kind` ∈ `{"postgres", "memory"}`.

- [ ] **Step 1: Installa le dipendenze (locale, `requirements.txt` è gitignored)**

Run: `pip install "langgraph-checkpoint-postgres" "psycopg[binary,pool]"`
Poi aggiungi a `requirements.txt` (file locale, non committato):

```text
langgraph-checkpoint-postgres
psycopg[binary,pool]
```

Expected: installazione completata. Se fallisce, prosegui comunque: il fallback `MemorySaver` mantiene il sistema funzionante e il test dello Step 2 lo verifica.

- [ ] **Step 2: Scrivi il test del selettore (deve fallire)**

Create `tests/test_checkpointer.py`:

```python
from langgraph.checkpoint.memory import MemorySaver

import agent


def test_build_checkpointer_memory_when_no_db():
    saver, kind = agent.build_checkpointer(None)
    assert kind == "memory"
    assert isinstance(saver, MemorySaver)


def test_build_checkpointer_memory_on_bad_uri():
    """URI non valido: nessuna eccezione, fallback a memoria."""
    saver, kind = agent.build_checkpointer("postgresql://nobody@127.0.0.1:1/none")
    assert kind == "memory"
    assert isinstance(saver, MemorySaver)
```

- [ ] **Step 3: Esegui il test per verificare che fallisca**

Run: `python -m pytest tests/test_checkpointer.py -q`
Expected: FAIL con `AttributeError: module 'agent' has no attribute 'build_checkpointer'`.

- [ ] **Step 4: Implementa in `agent/__init__.py`**

Aggiungi l'import in cima, insieme agli altri `from .`:

```python
from .conversations import ensure_schema
```

Aggiungi la funzione subito **prima** della creazione di `_graph` (che oggi usa `MemorySaver()`):

```python
def build_checkpointer(db_uri):
    """Checkpointer persistente su Postgres; fallback a MemorySaver se non disponibile."""
    if db_uri:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            saver_cm = PostgresSaver.from_conn_string(db_uri)
            saver = saver_cm.__enter__()   # tenuto aperto per la vita del processo
            saver.setup()
            return saver, "postgres"
        except Exception as exc:  # noqa: BLE001 - dipendenza assente o DB irraggiungibile
            log.warning("Postgres checkpointer non disponibile (%s); uso MemorySaver", exc)
    return MemorySaver(), "memory"
```

Sostituisci la riga che costruisce il grafo:

```python
_checkpointer, _checkpointer_kind = build_checkpointer(config.db_uri if engine is not None else None)
log.info("Checkpointer: %s", _checkpointer_kind)

_graph = build_graph(llm=text_llm, tools=_graph_tools, ground_fn=_ground,
                     checkpointer=_checkpointer)
```

E, subito dopo il blocco `try/except` che inizializza il DB (dove viene loggato "DB connected"), aggiungi la creazione delle tabelle applicative:

```python
if engine is not None:
    try:
        ensure_schema(engine, config.schema)
    except Exception as exc:  # noqa: BLE001 - non bloccare l'avvio
        log.error("ensure_schema failed: %s", exc)
```

- [ ] **Step 5: Esegui i test**

Run: `python -m pytest tests/test_checkpointer.py -q`
Expected: PASS (2 passed).

Run: `python -c "import agent; print('ok')"`
Expected: stampa `ok` (con log `Checkpointer: postgres` se DB e dipendenze ci sono, altrimenti `memory`).

- [ ] **Step 6: Commit**

```bash
git add agent/__init__.py tests/test_checkpointer.py
git commit -m "feat(agent): checkpointer Postgres con fallback MemorySaver + ensure_schema"
```

---

## Task 3: `run()` con conversation_id

**Files:**
- Modify: `agent/__init__.py`

**Interfaces:**
- Produces: `run(message, session_id, image=None, mime_type="image/jpeg", resume=None, viewport=None, conversation_id=None) -> {"text","geojson","awaiting_input"}` — usa `conversation_id` come `thread_id` quando presente, altrimenti `session_id`.

- [ ] **Step 1: Modifica la firma e il thread_id**

In `agent/__init__.py`, sostituisci la firma di `run` e la riga che costruisce `cfg`:

```python
def run(message, session_id, image=None, mime_type="image/jpeg", resume=None,
        viewport=None, conversation_id=None):
```

e

```python
    thread_id = conversation_id or session_id
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": config.recursion_limit}
```

Nel ramo "fresh input", sostituisci `"session_id": session_id` con `"session_id": thread_id`.

- [ ] **Step 2: Verifica che la suite resti verde**

Run: `python -m pytest tests/ -q`
Expected: PASS (tutti i test esistenti + i nuovi).

- [ ] **Step 3: Commit**

```bash
git add agent/__init__.py
git commit -m "feat(agent): run() accetta conversation_id come thread_id"
```

---

## Task 4: Endpoint conversazioni

**Files:**
- Modify: `server.py`

**Interfaces:**
- Consumes: `agent.conversations.*`, `agent.engine`, `agent.config.schema`.
- Produces: 5 endpoint REST (POST/GET/GET messages/PATCH/DELETE) + `ChatRequest.conversation_id`.

- [ ] **Step 1: Aggiungi import e modelli**

In `server.py`, dopo `import agent`, aggiungi:

```python
from agent import conversations as convo
```

E dopo la classe `ChatRequest`, aggiungi i modelli:

```python
class ConversationCreate(BaseModel):
    operator_id: str


class ConversationRename(BaseModel):
    title: str
```

Aggiungi il campo a `ChatRequest`:

```python
    conversation_id: str | None = None
```

- [ ] **Step 2: Aggiungi l'helper e gli endpoint**

Aggiungi in `server.py`, subito prima di `@app.post("/api/chat")`:

```python
def _require_db():
    if agent.engine is None:
        raise HTTPException(status_code=503, detail="Database offline: conversazioni non disponibili.")
    return agent.engine, agent.config.schema


@app.post("/api/conversations")
async def create_conversation_endpoint(req: ConversationCreate):
    engine, schema = _require_db()
    return convo.create_conversation(engine, schema, req.operator_id)


@app.get("/api/conversations")
async def list_conversations_endpoint(operator_id: str):
    engine, schema = _require_db()
    return convo.list_conversations(engine, schema, operator_id)


@app.get("/api/conversations/{conversation_id}/messages")
async def conversation_messages_endpoint(conversation_id: str):
    engine, schema = _require_db()
    if convo.get_conversation(engine, schema, conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversazione non trovata.")
    return convo.get_messages(engine, schema, conversation_id)


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation_endpoint(conversation_id: str, req: ConversationRename):
    engine, schema = _require_db()
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Titolo vuoto.")
    if not convo.rename_conversation(engine, schema, conversation_id, title[:120]):
        raise HTTPException(status_code=404, detail="Conversazione non trovata.")
    return {"status": "ok"}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    engine, schema = _require_db()
    if not convo.delete_conversation(engine, schema, conversation_id):
        raise HTTPException(status_code=404, detail="Conversazione non trovata.")
    return {"status": "ok"}
```

- [ ] **Step 3: Verifica l'import del server**

Run: `python -c "import server; print('server import ok')"`
Expected: stampa `server import ok`.

- [ ] **Step 4: Commit**

```bash
git add server.py
git commit -m "feat(server): endpoint CRUD conversazioni"
```

---

## Task 5: `/api/chat` salva i messaggi e il titolo

**Files:**
- Modify: `server.py`

**Interfaces:**
- Consumes: `convo.append_message`, `convo.get_conversation`, `convo.rename_conversation`, `convo.derive_title`, `convo.DEFAULT_TITLE`.

- [ ] **Step 1: Aggiorna il corpo di `/api/chat`**

Sostituisci il blocco `try: return agent.run(...) except ...` con:

```python
    conversation_id = request.conversation_id
    persist = conversation_id is not None and agent.engine is not None

    if persist and request.message:
        try:
            convo.append_message(agent.engine, agent.config.schema,
                                 conversation_id, "user", request.message)
        except Exception as e:  # noqa: BLE001 - la persistenza non deve bloccare la chat
            print(f"Persist user message failed: {e}")
            persist = False

    try:
        result = agent.run(
            message=request.message,
            session_id=session_id,
            image=image_bytes,
            mime_type=mime_type,
            resume=request.resume,
            viewport=request.viewport,
            conversation_id=conversation_id,
        )
    except Exception as e:
        print(f"Chat Error: {e}")
        return {"text": f"SYSTEM_FAILURE: {e}", "geojson": None, "awaiting_input": False}

    if persist:
        try:
            convo.append_message(agent.engine, agent.config.schema, conversation_id,
                                 "assistant", result.get("text", ""), result.get("geojson"))
            current = convo.get_conversation(agent.engine, agent.config.schema, conversation_id)
            if current and current["title"] == convo.DEFAULT_TITLE and request.message:
                convo.rename_conversation(agent.engine, agent.config.schema, conversation_id,
                                          convo.derive_title(request.message))
        except Exception as e:  # noqa: BLE001
            print(f"Persist assistant message failed: {e}")

    return result
```

- [ ] **Step 2: Verifica l'import e la suite**

Run: `python -c "import server; print('server import ok')"`
Expected: stampa `server import ok`.

Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat(server): /api/chat persiste i messaggi e genera il titolo"
```

---

## Task 6: Login salva l'operatore

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Salva `operator_id` al login**

In `index.html`, nel blocco `setTimeout` del login riuscito, accanto a `sessionStorage.setItem('intel_token', data.token);` aggiungi:

```javascript
                        localStorage.setItem('aegis_operator_id', operatorId);
```

- [ ] **Step 2: Verifica manuale**

Apri `index.html`, fai login con `OP_ADMIN` / `aegis2026` e verifica in DevTools → Application → Local Storage che `aegis_operator_id` sia valorizzato. (Richiede server + DB attivi; se non disponibili, salta e annota.)

- [ ] **Step 3: Commit**

> Nota: `index.html` può contenere WIP dell'utente. Se `git status` mostra altre modifiche non tue nel file, NON committare: lascia la modifica applicata e segnalalo. Altrimenti:

```bash
git add index.html
git commit -m "feat(ui): salva operator_id al login"
```

---

## Task 7: Sidebar conversazioni (markup + stile)

**Files:**
- Modify: `aegis.html`, `css/style.css`

- [ ] **Step 1: Aggiungi il blocco conversazioni in `aegis.html`**

In `aegis.html`, subito **prima** di `<div id="chat-history" ...>`, inserisci:

```html
            <div class="mb-4">
                <button id="new-chat-btn" type="button"
                        class="w-full bg-amber-600/20 hover:bg-amber-600/40 border border-amber-500/40 text-amber-400 py-2 mb-2 uppercase font-['Chakra_Petch'] text-xs tracking-widest transition-colors">
                    + NUOVA CHAT
                </button>
                <div id="conversation-list" class="conversation-list space-y-1 max-h-40 overflow-y-auto scrollbar-custom"></div>
            </div>
```

- [ ] **Step 2: Aggiungi lo stile in `css/style.css`**

Aggiungi in fondo a `css/style.css`:

```css
/* --- Lista conversazioni (sidebar) --- */
.conversation-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.5rem;
    border-left: 2px solid transparent;
    cursor: pointer;
    font-family: 'Chakra Petch', sans-serif;
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.7);
    transition: background 0.15s, border-color 0.15s;
}
.conversation-item:hover { background: rgba(245, 158, 11, 0.08); }
.conversation-item.active {
    background: rgba(245, 158, 11, 0.12);
    border-left-color: var(--amber);
    color: #fff;
}
.conversation-item .title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.conversation-item .actions { display: none; gap: 0.25rem; }
.conversation-item:hover .actions { display: flex; }
.conversation-item .actions button {
    background: none;
    border: none;
    color: rgba(255, 255, 255, 0.5);
    cursor: pointer;
    font-size: 0.7rem;
    padding: 0 0.15rem;
}
.conversation-item .actions button:hover { color: var(--amber); }
```

- [ ] **Step 3: Verifica visiva**

Apri `aegis.html` nel browser: il pulsante `+ NUOVA CHAT` compare in cima alla sidebar e la lista è vuota (verrà popolata nel Task 8).

- [ ] **Step 4: Commit**

> Nota: `aegis.html` e `css/style.css` possono contenere WIP dell'utente. Se `git status` mostra modifiche non tue in questi file, NON committare: lascia le modifiche applicate e segnalalo. Altrimenti:

```bash
git add aegis.html css/style.css
git commit -m "feat(ui): blocco conversazioni nella sidebar"
```

---

## Task 8: Logica conversazioni nel frontend

**Files:**
- Modify: `js/script.js`

**Interfaces:**
- Consumes: endpoint del Task 4/5.
- Produces: `currentConversationId` (stato), `loadConversations()`, `openConversation(id)`, `createConversation()`, `renameConversation(id, title)`, `deleteConversation(id)`.

- [ ] **Step 1: Aggiungi stato e funzioni**

In `js/script.js`, subito dopo la funzione `getSessionId()`, inserisci:

```javascript
// --- CONVERSAZIONI ---
const API_BASE = 'http://localhost:8000';
let currentConversationId = null;

function getOperatorId() {
    return localStorage.getItem('aegis_operator_id') || 'ANONYMOUS';
}

async function createConversation() {
    const res = await fetch(`${API_BASE}/api/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operator_id: getOperatorId() })
    });
    if (!res.ok) throw new Error('create failed');
    const conv = await res.json();
    currentConversationId = conv.id;
    clearChatHistory();
    await loadConversations();
    return conv;
}

function clearChatHistory() {
    const history = document.getElementById('chat-history');
    if (history) history.innerHTML = '';
    awaitingClarification = false;
}

async function loadConversations() {
    const list = document.getElementById('conversation-list');
    if (!list) return;
    let items = [];
    try {
        const res = await fetch(`${API_BASE}/api/conversations?operator_id=${encodeURIComponent(getOperatorId())}`);
        if (!res.ok) throw new Error('list failed');
        items = await res.json();
    } catch (e) {
        list.innerHTML = '<div class="text-[10px] text-amber-500/50 font-mono px-2">ARCHIVIO NON DISPONIBILE</div>';
        return;
    }
    list.innerHTML = '';
    items.forEach(conv => {
        const row = document.createElement('div');
        row.className = 'conversation-item' + (conv.id === currentConversationId ? ' active' : '');
        row.innerHTML = `<span class="title"></span>
            <span class="actions">
                <button type="button" data-act="rename" title="Rinomina">✎</button>
                <button type="button" data-act="delete" title="Elimina">🗑</button>
            </span>`;
        row.querySelector('.title').innerText = conv.title;
        row.addEventListener('click', (ev) => {
            const act = ev.target.dataset ? ev.target.dataset.act : null;
            if (act === 'rename') { ev.stopPropagation(); renameConversation(conv.id, conv.title); }
            else if (act === 'delete') { ev.stopPropagation(); deleteConversation(conv.id); }
            else { openConversation(conv.id); }
        });
        list.appendChild(row);
    });
}

async function openConversation(id) {
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${id}/messages`);
        if (!res.ok) throw new Error('messages failed');
        const msgs = await res.json();
        currentConversationId = id;
        clearChatHistory();
        msgs.forEach(m => addMessage(m.content, m.role === 'user' ? 'user' : 'ai'));
        await loadConversations();
    } catch (e) {
        addMessage('ARCHIVIO NON DISPONIBILE: impossibile aprire la conversazione.', 'ai');
    }
}

async function renameConversation(id, currentTitle) {
    const title = prompt('Nuovo titolo:', currentTitle);
    if (title === null) return;
    if (!title.trim()) return;
    await fetch(`${API_BASE}/api/conversations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim() })
    });
    await loadConversations();
}

async function deleteConversation(id) {
    if (!confirm('Eliminare questa conversazione?')) return;
    await fetch(`${API_BASE}/api/conversations/${id}`, { method: 'DELETE' });
    if (id === currentConversationId) {
        currentConversationId = null;
        clearChatHistory();
    }
    await loadConversations();
}

async function initConversations() {
    const btn = document.getElementById('new-chat-btn');
    if (btn) btn.addEventListener('click', () => createConversation().catch(() => {}));
    await loadConversations();
    if (!currentConversationId) {
        try { await createConversation(); } catch (e) { /* DB offline: chat effimera */ }
    }
}

initConversations();
```

- [ ] **Step 2: Invia `conversation_id` in `sendMessage`**

Nel `payload` di `sendMessage`, aggiungi il campo:

```javascript
            conversation_id: currentConversationId,
```

- [ ] **Step 3: Aggiorna la lista dopo la risposta**

In `sendMessage`, subito dopo `awaitingClarification = Boolean(data.awaiting_input);`, aggiungi:

```javascript
        loadConversations();   // il titolo può essere appena stato generato
```

- [ ] **Step 4: Verifica sintassi**

Run: `node --check js/script.js`
Expected: nessun output (sintassi valida).

- [ ] **Step 5: Verifica manuale end-to-end**

Con DB, Ollama e `python server.py` attivi: apri `aegis.html`, crea una chat, invia *"traccia via Dante"*, verifica che il titolo diventi "traccia via Dante", **riavvia il server**, ricarica la pagina e riapri la conversazione: i messaggi ci sono. (Se i servizi non sono disponibili, salta e annota.)

- [ ] **Step 6: Commit**

> Nota: `js/script.js` contiene WIP dell'utente. Se `git status` mostra modifiche non tue nel file, NON committare: lascia la modifica applicata e segnalalo. Altrimenti:

```bash
git add js/script.js
git commit -m "feat(ui): gestione conversazioni nella sidebar"
```

---

## Task 9: Documentazione

**Files:**
- Modify: `arch.md`

- [ ] **Step 1: Aggiungi la sezione conversazioni**

In `arch.md`, nella tabella dei moduli di §2, aggiungi la riga:

```markdown
| `conversations.py` | Persistenza delle chat: CRUD conversazioni/messaggi in `schema1` + `derive_title` (titolo automatico). |
```

E aggiungi una nuova sezione prima di "## 12. Limiti noti":

```markdown
## 11-bis. Conversazioni persistenti

Le chat sono salvate in due tabelle applicative (`schema1.conversations`, `schema1.messages`), create in modo idempotente all'avvio (`ensure_schema`). Ogni conversazione appartiene a un `operator_id` (quello del login) e ha un titolo generato dal primo messaggio (`derive_title`).

Il **checkpointer** di LangGraph usa Postgres quando disponibile (`build_checkpointer`), con `thread_id = conversation_id`: contesto e chiarimenti in sospeso sopravvivono al riavvio del server. Se le dipendenze o il DB mancano, si degrada a `MemorySaver` (memoria volatile) senza bloccare l'app.

La sidebar permette di creare, elencare, aprire, rinominare ed eliminare le conversazioni; `/api/chat` salva i messaggi e aggiorna il titolo al primo scambio.
```

- [ ] **Step 2: Aggiorna i limiti noti**

Nella §12 di `arch.md`, aggiungi:

```markdown
- **`operator_id` non è verificato**: separa le conversazioni per operatore ma, senza autenticazione reale, un client può richiedere l'elenco di un altro `operator_id`. L'auth (JWT/sessioni) resta una feature a parte.
- **Riapertura chat**: vengono ricaricati i messaggi, non i layer GeoJSON storici sulla mappa (il GeoJSON è salvato ma non ridisegnato).
```

- [ ] **Step 3: Suite completa finale**

Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add arch.md
git commit -m "docs(arch): conversazioni persistenti"
```

---

## Self-Review

**Spec coverage:**
- §2.1 tabelle → Task 1 (DDL + `ensure_schema`). ✓
- §2.2 modulo conversations → Task 1. ✓
- §2.3 checkpointer + fallback → Task 2; `thread_id = conversation_id` → Task 3. ✓
- §2.4 API (5 endpoint) → Task 4; `/api/chat` con persistenza e titolo → Task 5. ✓
- §2.5 login `operator_id` → Task 6; sidebar → Task 7; logica JS → Task 8. ✓
- §3 errori (503, 404, 400, fallback) → Task 4 (`_require_db`, 404/400), Task 2 (fallback), Task 5 (persistenza non bloccante). ✓
- §4 testing → Task 1 (derive_title puro + CRUD con skip), Task 2 (selettore checkpointer). ✓
- §7 criteri di successo → verifica manuale in Task 8 Step 5 (riavvio server + riapertura chat). ✓

**Placeholder scan:** nessun TBD/TODO; ogni step ha codice completo o comando concreto. Le note "se il file contiene WIP dell'utente non committare" sono istruzioni operative deliberate, non placeholder. ✓

**Type consistency:** le funzioni di `conversations.py` prendono sempre `(engine, schema, ...)` in Task 1/4/5; `build_checkpointer(db_uri) -> (saver, kind)` coerente tra Task 2 e i test; `conversation_id` è il nome usato in `run()` (Task 3), `ChatRequest` (Task 4), payload JS (Task 8); `currentConversationId` è l'unico nome di stato lato client; `DEFAULT_TITLE` usato in Task 1 e Task 5. ✓

> **Nota vs spec:** la spec ipotizzava `list_conversations(engine, operator_id)`; il piano aggiunge ovunque il parametro `schema` per rispettare il vincolo globale "mai hardcodare `schema1` nel Python". Equivalente funzionalmente.
