# A.E.G.I.S. — Vie intere via Overpass (ibrido)

**Data:** 2026-07-25
**Stato:** Design approvato
**Scope:** Layer agente (`agent/`). Completa il tracciamento delle **strade** (via intera) mantenendo Nominatim per aree/POI. `server.py`/`js`/prompt invariati.

---

## 1. Problema

*"traccia Via Monte Napoleone"* disegna solo un **tratto**. Nominatim, per una via, ritorna un solo *way* di OSM; le strade sono spezzate in più tratti agli incroci.

Evidenze (verificate dal vivo):
- Nominatim già **completo** per aree/strutture: *Prato della Valle* → Polygon a 6 anelli, *Parco Sempione*/*Duomo* → Polygon completi.
- Nominatim **incompleto** solo per le strade (1 tratto, 3 vertici).
- Overpass per *"Via Monte Napoleone"* → **6 tratti / 20 vertici** = via intera.

## 2. Obiettivo

Approccio **ibrido**: Nominatim resta la sorgente (geocoding + geometria completa di piazze/parchi/edifici); **Overpass usato SOLO per le strade** per unire tutti i tratti → via intera. Fallback a Nominatim se Overpass fallisce.

---

## 3. Architettura

### 3.1 `agent/overpass.py` (nuovo)
- `fetch_street(name: str, bbox, *, http_post=None) -> dict | None`
  - `bbox` in ordine **Overpass**: `(south, west, north, east)`.
  - query: `[out:json][timeout:25];(way["name"="<name>"]["highway"](<s,w,n,e>););out geom;` (nome con doppi apici escapati).
  - unisce la `geometry` di tutti i *way* in una **MultiLineString** GeoJSON (`{"type":"MultiLineString","coordinates":[[[lon,lat],...], ...]}`).
  - ritorna la geometria, o `None` se nessun *way* / errore / risposta non-JSON (rate-limit).
  - `http_post(url, data, headers, timeout) -> json` iniettabile → test **senza rete**.
- `resolve_place(query: str, viewbox=None, *, geocode_fn=geocode, street_fn=fetch_street) -> dict | None`
  - geocodifica con Nominatim (`geocode_fn`) → `{name, lat, lon, geometry}` (o `None`).
  - **solo se** `geometry["type"] == "LineString"` (una strada): calcola il `bbox` (da `viewbox` `(w,n,e,s)` → `(s,w,n,e)`; se `viewbox` assente, ±0.02° attorno al punto) e chiama `street_fn(street_name, bbox)`; se ritorna una MultiLineString, **sostituisce** `geometry` con essa. `street_name = name.split(",")[0].strip()`.
  - altrimenti (Polygon/Point) → lascia la geometria di Nominatim.
  - stessa firma/shape di `geocode` (`(query, viewbox) -> {name,lat,lon,geometry}`) → i tool non cambiano.

### 3.2 Wiring (`agent/__init__.py`)
- `make_graph_tools(..., geocode_fn=resolve_place)` al posto di `geocode`.
- `locate_place` / `buffer_around` **invariati**; il buffer su una MultiLineString funziona già (shapely).

### 3.3 Invariati
- `geocode.py` (Nominatim, ritorna già la geometria), `geometry.py`, `tools.py`, `prompts.py`, `server.py`, `js`.

---

## 4. Flusso

```
"traccia Via Monte Napoleone"
  → resolve_place
      → Nominatim: geometry = LineString (1 tratto)  → è una strada
      → Overpass fetch_street: MultiLineString (tutti i tratti)  → sostituisce
  → locate_place: FeatureCollection della VIA INTERA

"contorno di Prato della Valle"
  → resolve_place → Nominatim: Polygon (6 anelli) → NON è LineString → Overpass saltato
  → locate_place: il Polygon reale della piazza
```

---

## 5. Gestione errori

| Caso | Comportamento |
|---|---|
| Overpass timeout / rate-limit / non-JSON | `fetch_street` → `None` → `resolve_place` tiene la LineString di Nominatim (tratto) |
| Nessun *way* con quel nome nel bbox | `None` → fallback Nominatim |
| Geometria non-strada (Polygon/Point) | Overpass non chiamato |
| Nominatim fallisce | `resolve_place` → `None` → tool → `GEOCODE_FAILED` → `request_clarification` |

---

## 6. Testing (offline, con fake HTTP)

- `fetch_street`: fake `http_post` con più *way* → MultiLineString con tutti i tratti; risposta vuota → `None`; eccezione → `None`; la query contiene il bbox e il nome corretti.
- `resolve_place`:
  - Nominatim LineString + `street_fn` → MultiLineString ⇒ geometria **sostituita**;
  - Nominatim Polygon ⇒ `street_fn` **non** chiamato, Polygon invariato;
  - `street_fn` ritorna `None` ⇒ **fallback** alla LineString di Nominatim;
  - Nominatim `None` ⇒ `None`.
- Tool esistenti (`locate_place`/`buffer_around`) restano verdi (nessuna modifica).

---

## 7. Fuori scope (YAGNI)

- Overpass per aree/POI (Nominatim già completo).
- Libreria `osm2geojson` / assemblaggio multipolygon (non serve: solo *way*→MultiLineString).
- Stitching ordinato dei tratti in un'unica LineString (la MultiLineString rende/bufferizza bene così).
- Caching, provider alternativi.

---

## 8. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| Overpass pubblico lento / rate-limit | chiamato **solo per le strade**, una query, timeout, fallback a Nominatim |
| Nome via con caratteri speciali | escape dei doppi apici nella query |
| Vie omonime in altre zone | query **bbox-bounded** (viewport o intorno al punto) |
| MultiLineString non renderizzabile/bufferizzabile | Leaflet e shapely la gestiscono nativamente |

---

## 9. Criteri di successo

- *"traccia Via Monte Napoleone"* traccia la **via intera** (tutti i tratti), non un segmento.
- *"contorno di Prato della Valle"* resta il **Polygon completo** (nessuna regressione sulle aree).
- Overpass giù/rate-limited → si degrada al tratto di Nominatim, niente crash.
- Suite esistente verde + nuovi test (offline).
