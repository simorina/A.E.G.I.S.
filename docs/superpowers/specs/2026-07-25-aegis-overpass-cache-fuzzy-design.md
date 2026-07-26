# A.E.G.I.S. — Overpass: cache + fuzzy match dei nomi

**Data:** 2026-07-25
**Stato:** Design approvato
**Scope:** `agent/overpass.py` (+ test). Interfaccia dei tool invariata.

---

## 1. Problema

- Tracciando più vie in sequenza, Overpass pubblico rate-limita → richieste ripetute costose.
- Il match dei nomi è **esatto** (`["name"="X"]`): nomi leggermente diversi (es. *"Corso Vittorio Emanuele"* vs OSM *"Corso Vittorio Emanuele II"*) non vengono trovati → "buco" nel batch.

## 2. Obiettivo

1. **Cache** delle risposte Overpass (meno rate-limit, più veloce).
2. **Fuzzy match** dei nomi: abbinare i nomi richiesti ai nomi **reali** delle vie nella vista, tollerando maiuscole/piccole differenze/refusi.

Interfaccia `fetch_streets(names, bbox)` / `fetch_street(name, bbox)` invariata → `tools.py`/`__init__.py` non cambiano.

---

## 3. Architettura (`agent/overpass.py`)

### 3.1 Cache
- `_cache: dict[str, dict]` (chiave = stringa query). `_overpass_request` ritorna il valore cachato se presente; altrimenti richiede e **cacha solo le risposte riuscite** (i fallimenti non si cachano, così un retry successivo può riuscire). Session-scoped, dict semplice (YAGNI su TTL/size).

### 3.2 Fuzzy match (batch)
- `_street_names_in_bbox(bbox, post, sleep) -> list[str]` — query leggera `way["name"]["highway"](bbox);out tags;` → lista ordinata dei **nomi reali** delle vie nella vista (via `_overpass_request`, quindi cachata).
- `_match_names(requested, available, cutoff=0.8) -> dict[str, str]` — per ogni nome richiesto, `difflib.get_close_matches` **case-insensitive** (lowercase su entrambi i lati, mappa al nome originale) sopra `cutoff` → `{richiesto: nome_OSM_reale}`. Sotto soglia → scartato.
- `fetch_streets(names, bbox, *, http_post, sleep)` riscritto:
  1. `available = _street_names_in_bbox(bbox)`; se vuoto → `{}`.
  2. `matched = _match_names(names, available)` → nomi OSM reali abbinati.
  3. query geometria (esatta, i nomi ora sono reali) per i soli nomi abbinati → `out geom`.
  4. raggruppa per nome (`_ways_by_name`) → `{nome_OSM: MultiLineString}`.
  - Risultato **chiavato sul nome OSM reale** (etichette corrette). I richiesti non abbinati restano fuori (l'agente li vede nel `summary`).

### 3.3 Path singolo
- `fetch_street(name, bbox)` → match **case-insensitive** ancorato: `["name"~"^<name>$",i]` (regex-escape del nome + escape dei `"`). `resolve_place` già canonicalizza via Nominatim, quindi qui basta questo.

---

## 4. Errori / edge

| Caso | Comportamento |
|---|---|
| Overpass giù / rate-limit | `_overpass_request` → None (throttle+retry già presenti); `fetch_streets` → `{}`, `fetch_street` → None → fallback Nominatim |
| Nessun nome in vista | `_street_names_in_bbox` → `[]` → `fetch_streets` `{}` |
| Nessun match sopra soglia | `{}` (l'agente lo segnala) |
| Nome con caratteri regex/apici | `re.escape` + escape dei `"` |

---

## 5. Testing (offline, fake HTTP)

- **cache**: stessa query due volte → `http_post` chiamato **una** volta; un fallimento **non** viene cachato. (fixture che azzera `_cache`/`_state` a ogni test).
- `_street_names_in_bbox`: parsing dei `tags.name`.
- `_match_names`: match sopra soglia (case + differenza minima, es. "…Emanuele" → "…Emanuele II"), niente match sotto soglia.
- `fetch_streets` **fuzzy end-to-end**: fake HTTP che distingue la query `out tags` (ritorna i nomi) da `out geom` (ritorna le geometrie) → un nome richiesto leggermente diverso viene abbinato al nome reale.
- `fetch_street`: la query contiene il match **case-insensitive** (`~"^…$",i`); test esistente aggiornato.
- test esistenti di `fetch_streets`/`resolve_place` restano verdi (il fuzzy è trasparente per i match esatti).

---

## 6. Fuori scope (YAGNI)

- TTL / eviction della cache (dict di sessione).
- Cache persistente su disco/Redis.
- Match fuzzy oltre il bbox della vista (evita omonimie altrove).
- Overpass self-hosted (pezzo separato).

---

## 7. Criteri di successo

- *"traccia Corso Vittorio Emanuele"* (nome non esatto) → abbinato a *"Corso Vittorio Emanuele II"* e tracciato.
- Richieste ripetute nella stessa vista non ri-colpiscono Overpass (cache).
- Nessuna regressione: match esatti funzionano come prima; suite verde.
