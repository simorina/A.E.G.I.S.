# A.E.G.I.S. — Geolocalizzazione: geocoder + viewport

**Data:** 2026-07-25
**Stato:** Design approvato (in attesa di review finale dello spec)
**Scope:** Layer agente (`agent/`) + minime modifiche a `server.py` e `js/script.js`. Corregge il posizionamento errato delle geometrie disegnate da `draw_geometry`.

---

## 1. Problema

Chiedendo *"fai un'area attorno a Prato della Valle"* (Padova), l'agente ha disegnato il cerchio nel punto sbagliato. Cause:

1. **`draw_geometry` fa inventare le coordinate all'LLM.** La modalità geometria non geocodifica e non interroga il DB: chiede al modello di produrre direttamente `ST_MakePoint(lon, lat)`. Gli LLM sono imprecisi sulle coordinate esatte → punto sbagliato di centinaia di metri.
2. **Prompt e DB hardcodati su Milano.** `AGENT_SYSTEM_PROMPT`/`GEOMETRY_TEMPLATE` dicono *"city of Milan"* con esempi a coordinate milanesi; il DB contiene solo Milano → nessun ancoraggio per luoghi altrove.
3. **Il frontend non manda la vista della mappa.** L'agente non sa dove sta guardando l'operatore → non può fare *"attorno a qui"*.
4. **Nessun geocoder reale.**

---

## 2. Obiettivo

Le coordinate non devono più essere **indovinate** dall'LLM. Introduciamo:

- un **tool `geocode_place`** che risolve nomi → coordinate reali (Nominatim/OSM), che l'agente **concatena** prima di `draw_geometry` (pattern ReAct già esistente);
- il passaggio del **viewport** (centro + bounds della mappa) per gestire *"qui / quest'area"* e per **biasare** il geocoding sulla zona visibile;
- il **de-hardcoding di Milano** dai percorsi di geometria/geocoding.

Le coordinate reali arrivano all'agente in una `ToolMessage`; il modello le **ricopia** nella chiamata `draw_geometry` successiva (trascrizione, non memoria → affidabile).

---

## 3. Architettura

### 3.1 Geocoder (`agent/geocode.py`)
- `geocode(query: str, viewbox: tuple | None = None, *, geocoder=<default>) -> dict | None`
  - ritorna `{"name": str, "lat": float, "lon": float}` per il miglior match, `None` se nessuno.
  - backend **Nominatim** via `geopy`, con **User-Agent** conforme alla policy OSM e timeout.
  - se `viewbox` è passato, **bias** sulla zona visibile (senza `bounded` rigido: preferenza, non vincolo).
  - gestione errori: timeout / rete assente / nessun risultato → ritorna `None` (mai eccezione fuori dal modulo).
  - il `geocoder` è **iniettabile** → test senza rete.
- `current_viewport: ContextVar` — impostato da `run()` prima di `graph.invoke`, letto dal tool `geocode_place` per costruire il `viewbox`. Evita `InjectedState` (che vive in `langgraph.prebuilt`, incompatibile con lo stack — vedi vincolo del progetto).

### 3.2 Tool `geocode_place` (`agent/tools.py`, in `make_graph_tools`)
- `geocode_place(place: str) -> dict` con `{"summary": str, "geojson": None}`.
- successo → `summary = "GEOCODED: <name> -> lat=<lat>, lon=<lon>"`.
- fallimento → `summary = "GEOCODE_FAILED: '<place>' non trovato. Chiedi conferma delle coordinate all'operatore."`.
- legge il `viewbox` dal `current_viewport` (se presente) per il bias.

### 3.3 Viewport nello stato (`agent/graph.py`)
- `AgentState` acquisisce `viewport: Optional[dict]` (canale a sovrascrittura, nessun reducer).
- Forma: `{"lat": float, "lon": float, "north": float, "south": float, "east": float, "west": float}` (centro + bounds).
- Il nodo `agent` inietta nel system prompt, quando `viewport` è presente, una riga:
  `OPERATOR MAP VIEW: center lat=<lat> lon=<lon>; bounds N=<n> S=<s> E=<e> W=<w>.`
  Così per *"attorno a qui / quest'area"* il modello bufferizza attorno al **centro mappa**.

### 3.4 Prompt (`agent/prompts.py`)
- `AGENT_SYSTEM_PROMPT`: aggiunge `geocode_place` all'elenco tool e le regole:
  - luogo con nome (via/piazza/monumento) → **prima** `geocode_place`, poi `draw_geometry` con le coordinate ottenute;
  - *"qui / quest'area"* → usa il centro della OPERATOR MAP VIEW;
  - se `geocode_place` fallisce → `request_clarification` (non inventare coordinate);
  - raggio di default **500 m** se non specificato.
  - rimosso il vincolo *"city of Milan"* (l'agente non è più legato a una città per la geometria).
- `GEOMETRY_TEMPLATE`: rimosso il framing Milano; resta city-agnostic (costruisce geometrie dalle coordinate fornite).
- `_SQL_QUERY_TEMPLATE` / `query_intel`: **invariati** (il DB è Milano).

### 3.5 Wiring (`agent/__init__.py`)
- `run(message, session_id, image=None, mime_type="image/jpeg", resume=None, viewport=None)`.
- imposta `current_viewport` dal parametro `viewport` prima di `graph.invoke` (e lo azzera dopo, in `finally`).
- il turno nuovo include `"viewport": viewport` nello stato iniziale.
- `geocode_place` aggiunto ai `_graph_tools`; il geocoder reale iniettato nella factory.

### 3.6 Server (`server.py`)
- `ChatRequest` acquisisce `viewport: dict | None`.
- `/api/chat` passa `viewport=request.viewport` a `agent.run`.

### 3.7 Frontend (`js/script.js`)
- Nel `payload` di `/api/chat` aggiunge `viewport` da `map.getCenter()` + `map.getBounds()` (riusa il pattern di `performScan`):
  `{lat, lon, north, south, east, west}`.
- File nel WIP dell'utente → applicato ma **non committato**.

---

## 4. Flusso corretto (esempio)

```
"area attorno a Prato della Valle"
  → agent → geocode_place("Prato della Valle")   (viewbox = vista Padova)
  → "GEOCODED: Prato della Valle -> lat=45.398, lon=11.877"
  → agent → draw_geometry("buffer 500m at lat=45.398 lon=11.877")
  → ground → briefing + GeoJSON del cerchio centrato correttamente
```

---

## 5. Gestione errori

| Caso | Comportamento |
|---|---|
| Nominatim timeout / rete assente | `geocode` ritorna `None` → `geocode_place` → `GEOCODE_FAILED` → l'agente chiama `request_clarification` |
| Nessun match | come sopra |
| `viewport` assente (frontend vecchio o scan) | nessun bias, nessuna riga MAP VIEW; comportamento invariato |
| L'utente specifica già le coordinate | l'agente può saltare `geocode_place` e usarle direttamente |

---

## 6. Testing (offline, con fake geocoder)

- `geocode`: match → dict; nessun match → `None`; passaggio del `viewbox`; eccezione del client → `None`.
- `geocode_place`: successo (stringa GEOCODED) e fallimento (GEOCODE_FAILED); lettura del `current_viewport`.
- iniezione della riga OPERATOR MAP VIEW nel system prompt quando `viewport` è presente (e assenza quando è `None`).
- catena ReAct `geocode_place → draw_geometry` con LLM scriptato + geocoder fake (nessuna rete).
- i test esistenti restano verdi.

---

## 7. Fuori scope (YAGNI)

- Caching dei risultati di geocoding.
- Geocoder self-hosted / provider alternativi.
- UI di disambiguazione multi-risultato (si prende il primo match; se nessuno → chiarimento).
- Reverse-geocoding (coordinate → nome).

---

## 8. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Nominatim: rate limit / policy | User-Agent conforme, un solo request per geocodifica, timeout; è un uso demo a bassa frequenza |
| Rete assente (uso "tattico offline") | Fallimento con grazia → `request_clarification`; geometry con coordinate esplicite resta possibile |
| L'LLM non concatena geocode→draw | Regole esplicite nel system prompt + esempio; `temperature=0` |
| `viewbox` di Nominatim con ordine lon/lat errato | Costruzione centralizzata in `agent/geocode.py`, coperta da test |

---

## 9. Criteri di successo

- *"area attorno a Prato della Valle"* disegna il cerchio **centrato su Prato della Valle** (Padova), non altrove.
- *"disegna 500 m attorno a qui"* bufferizza attorno al **centro mappa** corrente.
- Un nome introvabile porta a una **domanda di chiarimento**, non a coordinate inventate.
- Nessuna regressione: suite esistente verde + nuovi test geocoding/viewport verdi (tutti offline).
