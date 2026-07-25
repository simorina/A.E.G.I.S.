# A.E.G.I.S. — Tool geo attivi anche col DB spento

**Data:** 2026-07-25
**Stato:** Design approvato
**Scope:** Layer agente (`agent/`). Sposta la guardia "DB offline" dal livello `run()` al livello dei soli tool che usano il DB.

---

## 1. Problema

`run()` blocca **ogni** richiesta testuale quando il DB è spento:

```python
if engine is None and image is None:
    return {"text": "Tactical engine offline.", ...}
```

Ma i tool basati su geocoding/OSM (`locate_place`, `buffer_around`, `trace_streets`) e la vision **non usano il DB**. Con la guardia attuale non partono nemmeno. Non si può decidere alla porta di `run()` quale tool verrà scelto (lo decide il grafo a runtime), quindi la guardia va spostata **sul tool DB**.

Nota: i tre tool SQL — `query_intel`, `spatial_analysis` **e `draw_geometry`** — passano tutti da `run_sql_pipeline` ed **eseguono SQL/PostGIS**, quindi richiedono il DB. I tool geo (locate/buffer/trace) no.

---

## 2. Design

1. **Rimuovere** l'early-return offline in `run()` → il grafo (e il fallback orchestrator) girano sempre per il testo; i tool geo funzionano senza DB.
2. **Degradare al livello del tool DB**: in `agent/__init__.py`, passare `execute_sql=None` a `make_graph_tools`/`make_tools` quando `engine is None`. In `run_sql_pipeline`, **prima del loop**, se `execute_sql is None` → ritornare subito:
   `{"summary": "DATABASE_OFFLINE: intel database non raggiungibile.", "geojson": None}`
   (zero chiamate LLM sprecate, niente `SYSTEM_FAILURE` con 3 retry).

**Effetto col DB spento:**
- funzionano: `locate_place`, `buffer_around`, `trace_streets`, vision;
- rispondono `DATABASE_OFFLINE` (pulito): `query_intel`, `spatial_analysis`, `draw_geometry`.

Approcci scartati: guardia "tool-aware" in `run()` (impossibile, il tool si sceglie a runtime); lasciare l'`AttributeError` corrente da `execute_readonly(None, ...)` (brutto, 3 retry).

---

## 3. File toccati

- `agent/tools.py` — `run_sql_pipeline`: short-circuit se `execute_sql is None`.
- `agent/__init__.py` — passare `execute_sql=(_execute_sql if engine is not None else None)` alle factory; rimuovere l'early-return offline in `run()`.

---

## 4. Testing (offline)

- `run_sql_pipeline(..., execute_sql=None)` → ritorna `DATABASE_OFFLINE` **senza** chiamare `generate` né `validate` (verificato con una `generate` che registra le chiamate).
- Test esistenti di `run_sql_pipeline`/tool (con `execute_sql` reale) invariati.
- Import smoke di `agent` invariato.

---

## 5. Fuori scope (YAGNI)

- Rendere `draw_geometry` indipendente dal DB calcolando la geometria in Python (shapely) invece che via PostGIS `ST_*`. Possibile miglioramento futuro; per ora resta DB-gated e riporta `DATABASE_OFFLINE`.

---

## 6. Criteri di successo

- Col DB spento, *"traccia Via Monte Napoleone"* / *"area attorno a X"* funzionano.
- Col DB spento, una query DB risponde `DATABASE_OFFLINE` in modo pulito (no `SYSTEM_FAILURE`, no 3 retry).
- Col DB su, nessun cambiamento di comportamento; suite esistente verde.
