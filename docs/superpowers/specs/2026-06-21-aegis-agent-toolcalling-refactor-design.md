# A.E.G.I.S. — Refactor dell'agente verso un'architettura a tool-calling

**Data:** 2026-06-21
**Stato:** Design approvato (in attesa di review finale dello spec)
**Scope:** Solo il layer agente (`agent.py` → package `agent/`) e le minime modifiche a `server.py` e `js/script.js` necessarie per la memoria conversazionale.

---

## 1. Obiettivo

Trasformare l'attuale `agent.py` monolitico in un **agente a tool-calling** modulare, sicuro e testabile. Il modello smette di scegliere la modalità tramite un mega-prompt con "MODE 1 / MODE 2" e diventa un orchestratore che **chiama tool distinti**, ciascuno con il proprio prompt focalizzato.

Le quattro priorità richieste, tutte in scope:

1. **Affidabilità SQL** — prompt focalizzati, few-shot per le query DB, parsing robusto, retry mirato.
2. **Sicurezza & guardrail** — sola lettura forzata su due livelli (validazione + transazione `READ ONLY`).
3. **Nuove capacità** — memoria conversazionale end-to-end, modello vision dedicato con fallback.
4. **Qualità del codice** — package modulare, config coerente, logging strutturato, unit test.

---

## 2. Stato attuale e problemi

`agent.py` è un singolo file che contiene config, connessione DB, init LLM, due funzioni core e i prompt/chain.

Problemi concreti individuati:

- **Sicurezza:** la SQL generata viene eseguita direttamente in `server.py` (`gpd.read_postgis`) senza alcun guardrail. Nulla impedisce `DROP`/`DELETE`/`UPDATE` se il modello o un prompt-injection li produce.
- **Config incoerente:** lo schema `schema1` è hardcoded nel prompt invece di `Config.SCHEMA`; il README parla di `qwen3-vl`/`llava`, `.env` usa `nemotron-3-ultra:cloud`; un solo `llm` globale serve SQL, summary e vision.
- **Parsing fragile:** `extract_sql_from_response` usa regex + primo `;`; il flag `{error}` convive in modo ambiguo con `create_sql_query_chain`.
- **Nessuna memoria:** ogni richiesta è stateless, niente follow-up tipo *"ora solo la linea M4"*.
- **Poca osservabilità:** `print()` sparsi, nessun logging strutturato né validazione input.
- **Prompt monolitico:** un unico template gestisce interrogazione DB *e* sintesi di geometrie, rendendolo lungo e difficile da far rispettare.

---

## 3. Approccio scelto

**Package modulare + orchestrazione a tool-calling custom.**

Si mantengono i primitivi LangChain leggeri (`ChatOllama`, prompt template, output parser) ma si **sostituisce `create_sql_query_chain`** con una pipeline esplicita. Il mega-prompt viene **spezzato** in tool separati legati al modello con `bind_tools` (function calling nativo di Ollama).

Approcci scartati:
- **A — Wrapper sopra le chain esistenti:** eredita l'ambiguità del `{error}` e dà poco controllo su memoria/guardrail.
- **B — Riscrittura full LangGraph:** dipendenza pesante e over-engineering per questo sistema.

---

## 4. Architettura — struttura del package

`agent.py` viene sostituito da un package `agent/`:

```
agent/
  __init__.py        # API pubblica per server.py (engine, run, analyze_satellite_image, ...)
  config.py          # .env + validazione; TEXT_MODEL / VISION_MODEL (fallback a MODEL_NAME)
  llm.py             # factory dei modelli (testo+tools, vision)
  db.py              # engine, SQLDatabase, table_info
  prompts.py         # prompt SPEZZATI: system agente, sql_query, geometry, vision, briefing
  safety.py          # guardrail SQL (single stmt, solo SELECT/WITH, blocco DDL/DML, allow-list schema)
  memory.py          # store conversazionale per session_id
  tools.py           # i 3 @tool: query_intel, draw_geometry, recon_image
  orchestrator.py    # loop tool-calling + fallback router + briefing finale
  vision.py          # analisi immagine (usata da recon_image e da /api/scan)
```

Ogni modulo ha una responsabilità singola e un'interfaccia chiara; le funzioni pure (`safety`, parsing, `memory`, `config`) sono testabili senza DB né LLM.

---

## 5. I tool

Ogni tool è una funzione decorata `@tool` (LangChain) con docstring che il modello usa per il routing.

### 5.1 `query_intel(question: str) -> ToolResult`
- **Scopo:** Database Intelligence (MODE 1). Trova/elenca/conta intel reale già nel DB.
- **Pipeline interna:** `genera SQL (prompt sql_query) → valida (safety) → esegue read-only → se errore, auto-corregge (max 3 tentativi con errore classificato)`.
- **Prompt dedicato:** solo interrogazione di `schema1`, con `table_info` e few-shot example. Schema iniettato da `Config.SCHEMA`.
- **Output:** righe (per il briefing) + GeoJSON (per la mappa).

### 5.2 `draw_geometry(spec: str) -> ToolResult`
- **Scopo:** Tactical Geometry (MODE 2). Disegna/crea/traccia una nuova forma (zona, perimetro, rotta, buffer) **senza** toccare il DB.
- **Prompt dedicato:** solo costruttori PostGIS (`ST_GeomFromText`, `ST_MakePoint`, `ST_MakeLine`, `ST_Buffer`), regole SRID 4326 e colonna `geom`, con esempi.
- **Output:** GeoJSON della geometria sintetizzata.

### 5.3 `recon_image(context: str) -> ToolResult`
- **Scopo:** Vision/GEOINT. Analizza l'immagine satellitare fornita dall'operatore.
- **Implementazione:** delega a `vision.analyze_satellite_image` con il **modello vision dedicato**.
- **Output:** report di ricognizione testuale (no GeoJSON).

**Vincoli comuni ai tool che producono geometria:** ogni risultato espone una colonna `geom` in SRID 4326 (l'API legge `geom_col='geom'`).

---

## 6. Orchestratore

`orchestrator.run(message: str, session_id: str, image: bytes | None = None) -> dict`

Flusso:
1. Carica la memoria della sessione (`memory.get(session_id)`).
2. Se è presente un'immagine → percorso diretto `recon_image` (nessun routing necessario).
3. Altrimenti: invia `system prompt agente + storia + richiesta` al modello con i tool legati (`bind_tools`).
4. Il modello emette una tool-call → l'orchestratore esegue il tool → restituisce il risultato al modello.
5. Il modello produce il **briefing** finale (persona Palantir/AEGIS) basato solo sui dati del tool.
6. L'orchestratore raccoglie il GeoJSON dal tool che l'ha prodotto e assembla `{ "text": briefing, "geojson": geojson | None }`.
7. Aggiorna la memoria (richiesta + risposta).

**Fallback (no native tool-calling):** allo startup `llm.py` verifica se `TEXT_MODEL` supporta i tool. Se non li supporta, l'orchestratore usa un **router a classificazione d'intento** (un prompt che mappa la richiesta su `query_intel` / `draw_geometry`) invece di `bind_tools`. Stessa interfaccia pubblica, comportamento equivalente.

---

## 7. Sicurezza (doppio strato)

**Strato 1 — validazione statica (`safety.validate_readonly_sql`):**
- La query deve essere una **singola** statement.
- Deve iniziare con `SELECT` o `WITH`.
- Blocco keyword pericolose: `INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE, COPY, CALL, DO, ;`-injection multipla.
- Allow-list dello schema: la query può riferirsi solo a `Config.SCHEMA`.
- In caso di violazione → `UnsafeQueryError` (la query non viene mai eseguita).

**Strato 2 — esecuzione difensiva (`db`):**
- Ogni query gira in una transazione `SET TRANSACTION READ ONLY`.
- `SET LOCAL statement_timeout = <N>ms` per evitare query lunghe/abusive.
- Difesa in profondità: anche se lo Strato 1 venisse aggirato, il DB rifiuta qualsiasi scrittura.

---

## 8. Memoria conversazionale (end-to-end)

- **`memory.py`:** store in-memory `dict[session_id] -> deque[(role, content)]` con cap (es. ultime 6 battute). API: `get`, `append`, `clear`.
- **Frontend (`js/script.js`):** genera un `session_id` (uuid) alla prima apertura, lo salva in `localStorage`, lo include nel payload di ogni `/api/chat`.
- **Server (`server.py`):** estrae `session_id` dalla request e lo passa a `orchestrator.run`.
- **Uso:** le ultime N battute entrano nel contesto dell'orchestratore così i follow-up ("ora solo M4") funzionano.

> Nota: store in-memory → la memoria si azzera al riavvio del server. Accettabile per questo sistema (nessuna persistenza richiesta — YAGNI).

---

## 9. Config e prompt

**Config (`config.py`):** carica e **valida** le env var; introduce `TEXT_MODEL` e `VISION_MODEL` (entrambi con fallback a `MODEL_NAME` se non specificati). Espone `SCHEMA`, `DB_URI`, `LLM_URL`, `STATEMENT_TIMEOUT_MS`, `MEMORY_TURNS`.

**Prompt (`prompts.py`)** — il monolite viene spezzato in:
- `AGENT_SYSTEM_PROMPT` — persona Palantir/AEGIS + istruzioni di routing + vincoli `geom`/SRID 4326.
- `SQL_QUERY_PROMPT` — solo MODE 1, con `{table_info}`, few-shot, schema iniettato.
- `GEOMETRY_PROMPT` — solo MODE 2, costruttori `ST_*` + esempi.
- `VISION_PROMPT` — ricognizione ottica.
- `BRIEFING_PROMPT` — sintesi tattica finale.

---

## 10. Modifiche a `server.py`

- `/api/chat` diventa sottile: legge `message`, `image_data`, `session_id` → chiama `orchestrator.run(...)` → ritorna `{text, geojson}`. Il retry loop a 3 tentativi **si sposta dentro l'agente** (`query_intel`).
- `/api/scan` continua a usare `vision.analyze_satellite_image` (via `recon_image` o direttamente) con il modello vision dedicato.
- `/api/login` invariato.
- `ChatRequest` acquisisce il campo `session_id: str | None`.

---

## 11. Osservabilità

- Sostituzione dei `print()` con il modulo `logging` (logger per modulo, livello configurabile).
- Log su: SQL generata, esito validazione safety, tool scelto, tentativi di auto-correzione, errori.

---

## 12. Testing

Unit test sulle funzioni pure (nessun DB/LLM richiesto):
- `safety.validate_readonly_sql`: accetta SELECT/WITH validi; rifiuta DDL/DML, multi-statement, schema fuori allow-list.
- parsing SQL: estrazione corretta da output con fence/prosa/`;`.
- `memory`: append/cap/get/clear.
- `config`: validazione env var, fallback dei modelli.

Smoke test dell'orchestratore con LLM/DB mockati: **opzionali** (best-effort), non bloccanti per il completamento.

---

## 13. Fuori scope (YAGNI)

- Persistenza della memoria su DB/Redis.
- Migrazione a LangGraph.
- Autenticazione/rate-limiting degli endpoint.
- Nuove tabelle o dati nel DB.
- Ridisegno del frontend oltre l'aggiunta del `session_id`.

---

## 14. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| `TEXT_MODEL` non supporta tool-calling nativo | Router a classificazione d'intento come fallback (§6) |
| `VISION_MODEL` non multimodale | `VISION_MODEL` separato in `.env`; fallback documentato (es. `llava`) |
| Regressioni negli import di `server.py` | `agent/__init__.py` espone un'API pubblica stabile |
| Guardrail aggirato da SQL creativa | Secondo strato `READ ONLY` lato DB (§7) |

---

## 15. Criteri di successo

- L'agente è un package modulare con responsabilità separate e prompt spezzati in tool.
- Una richiesta di scrittura/distruttiva non viene **mai** eseguita (test che lo dimostra).
- Un follow-up conversazionale ("ora solo M4") produce la query corretta.
- `server.py` è sottile: nessuna logica di retry/SQL al suo interno.
- Unit test verdi sulle funzioni pure.
