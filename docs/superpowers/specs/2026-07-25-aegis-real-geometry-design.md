# A.E.G.I.S. — Geometrie reali dei luoghi (tracciamento vie/aree)

**Data:** 2026-07-25
**Stato:** Design approvato (in attesa di review finale dello spec)
**Scope:** Layer agente (`agent/`). Estende il geocoding per usare la **geometria reale** dei luoghi. `server.py`/`js` invariati (il viewport è già inviato).

---

## 1. Problema

Chiedendo *"traccia Via Monte Napoleone"* l'agente ha disegnato una linea lungo la via **perpendicolare**. Causa (verificata dal vivo):

- `geocode_place` risolve un nome in **un solo punto** (`lat/lon`);
- per **tracciare una via** serve la sua **polilinea reale**; con un punto solo, `draw_geometry` **inventa** direzione e lunghezza della linea → orientamento sbagliato.
- Nominatim con `polygon_geojson=1` restituisce invece la **LineString reale** della via (e il **Polygon** per una piazza). Non la stiamo usando.

---

## 2. Obiettivo

Usare la **geometria reale** (OSM/Nominatim) dei luoghi con nome:

- *"traccia / contorno / segna X"* → la **geometria reale** (LineString/Polygon/Point) resa direttamente;
- *"area / raggio / entro N m attorno a X"* → **buffer** della geometria reale (default 500 m);
- geometrie **sintetiche** da coordinate esplicite → restano su `draw_geometry`.

Il buffer si calcola sulla **geometria reale** (non un cerchio su un punto), così *"area attorno a Prato della Valle"* avvolge davvero la piazza.

---

## 3. Architettura

### 3.1 Geocoder (`agent/geocode.py`, riscritto)
- Passa da geopy a **richieste dirette a Nominatim** (per ottenere la geometria).
- `geocode(query: str, viewbox=None, *, http_get=None) -> dict | None`
  - ritorna `{"name": str, "lat": float, "lon": float, "geometry": dict}` sul miglior match, `None` se assente/errore.
  - `geometry` = geometria GeoJSON restituita da Nominatim (`polygon_geojson=1`); se assente (POI senza geometria), **fallback a un Point** costruito da `lat/lon` → `geometry` è sempre un dict.
  - parametri Nominatim: `q`, `format=jsonv2`, `polygon_geojson=1`, `limit=1`; se `viewbox` → `viewbox=<w,n,e,s>` + `bounded=0` (bias, non vincolo). Header `User-Agent` conforme, timeout.
  - `http_get` è **iniettabile** (una callable `(url, params, headers, timeout) -> parsed_json`) → test **senza rete**.
- `current_viewport` (ContextVar) e `viewbox_from_viewport` **invariati**.

### 3.2 Helper geometrie (`agent/geometry.py`, nuovo)
- `feature_collection(geometry: dict, label: str) -> str` — incapsula una geometria GeoJSON in una `FeatureCollection` (stringa) con proprietà `label`.
- `buffer_geometry(geometry: dict, radius_m: float) -> str` — buffer metrico accurato: `shapely.shape` → `GeoSeries(crs=4326)` → riproiezione in **UTM** (`estimate_utm_crs`) → `.buffer(radius_m)` → ritorno in 4326 come `FeatureCollection` (stringa). Nessun DB (geometria da OSM).
- Funzioni **pure**, testabili offline (geopandas/shapely già installati).

### 3.3 Tool (`agent/tools.py`)
Sostituiscono `geocode_place`:

| Tool | Uso | Output (`geojson`) |
|---|---|---|
| `locate_place(place)` | traccia/contorno/segna una via/piazza/POI | `feature_collection(geometry, name)` — geometria reale |
| `buffer_around(place, radius_m=500)` | area/raggio/entro N m attorno a un luogo | `buffer_geometry(geometry, radius_m)` |

- Entrambi ritornano `{"summary": str, "geojson": str}`; il GeoJSON emerge sulla mappa automaticamente via il nodo `tools` (già così).
- Su geocoding fallito → `{"summary": "GEOCODE_FAILED: ...", "geojson": None}` e il system prompt istruisce l'agente a chiamare `request_clarification`.
- `geocode_fn` iniettabile nella factory (default: il geocoder reale). Gli helper `feature_collection`/`buffer_geometry` sono importati direttamente (puri).
- `draw_geometry` **invariato**: geometrie sintetiche da coordinate esplicite.
- `make_graph_tools` ritorna `[query_intel, draw_geometry, spatial_analysis, locate_place, buffer_around]` (+ `request_clarification` nel wiring).

### 3.4 Prompt (`agent/prompts.py`)
`AGENT_SYSTEM_PROMPT` aggiorna l'elenco tool e le regole:
- luogo con nome da **mostrare/tracciare** → `locate_place` (geometria reale, non ricostruirla);
- **area/raggio attorno a** un luogo con nome → `buffer_around` (default 500 m);
- `draw_geometry` SOLO per forme sintetiche da coordinate esplicite (corridoio tra coordinate, poligono con vertici dati, cerchio a coordinate date);
- `locate_place`/`buffer_around` falliti → `request_clarification` (niente coordinate inventate).

### 3.5 Wiring (`agent/__init__.py`)
- `make_graph_tools(..., geocode_fn=geocode)`; `run`/viewport/`current_viewport` invariati.

### 3.6 Server / Frontend
- **Invariati**: il `viewport` è già inviato e passato; nessuna nuova modifica.

---

## 4. Flusso corretto (esempi)

```
"traccia Via Monte Napoleone"
  → locate_place("Via Monte Napoleone")   (viewbox = vista Milano)
  → geometry = LineString reale della via  → FeatureCollection
  → briefing + la VIA giusta tracciata sulla mappa

"area di 300 m attorno a Prato della Valle"
  → buffer_around("Prato della Valle", 300)
  → geometry reale (Polygon della piazza) → buffer 300 m (UTM)
  → anello che avvolge la piazza
```

---

## 5. Gestione errori

| Caso | Comportamento |
|---|---|
| Nominatim timeout / rete assente / nessun match | `geocode` → `None` → tool → `GEOCODE_FAILED` → `request_clarification` |
| POI senza geometria OSM | `geometry` = Point da lat/lon; `locate_place` mostra il punto, `buffer_around` bufferizza il punto (cerchio) |
| `viewport` assente | nessun bias; comportamento invariato |
| geometria molto grande | gestita da shapely/geopandas senza problemi |

---

## 6. Testing (offline)

- `geocode`: fake `http_get` con risposta Nominatim (LineString) → `geometry` corretta; nessun risultato → `None`; passaggio del `viewbox`; **fallback Point** quando manca la geometria.
- `geometry.py`: `feature_collection` incapsula correttamente; `buffer_geometry` produce un **Polygon** con area coerente col raggio (bounds espansi).
- `tools`: `locate_place` (geojson = geometria reale), `buffer_around` (geojson = buffer), fallimento → `GEOCODE_FAILED`.
- `prompts`: menziona `locate_place` e `buffer_around`.
- test esistenti aggiornati: rimozione di `geocode_place` (test in `test_tools.py`/`test_geocode.py` riscritti sul nuovo seam); il resto verde.

---

## 7. Fuori scope (YAGNI)

- **Overpass API** per unire tutti i tratti di una via lunga (Nominatim può dare un solo *way*). Upgrade futuro.
- Caching, provider alternativi, reverse-geocoding.
- Disambiguazione multi-risultato (si prende il primo match; bias sul viewport).

---

## 8. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Via lunga → Nominatim ritorna un solo tratto | Accettato per la demo (comunque la via **giusta**); Overpass come upgrade |
| Distorsione metrica del buffer | Riproiezione in **UTM** (`estimate_utm_crs`), non Web Mercator |
| Riscrittura di `geocode.py` rompe l'esistente | `geocode()` mantiene firma compatibile (`viewbox`, iniettabile) + suite di test aggiornata |
| Nominatim policy/rate limit | User-Agent conforme, una richiesta per operazione, timeout; uso demo |

---

## 9. Criteri di successo

- *"traccia Via Monte Napoleone"* disegna la **via giusta** (LineString reale), non la perpendicolare.
- *"area attorno a Prato della Valle"* mostra un **buffer che avvolge la piazza reale**.
- Un nome introvabile → **domanda di chiarimento**, non coordinate inventate.
- Suite esistente verde + nuovi test (tutti offline).
