import logging
import time

from .geocode import geocode

log = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "aegis-geoint/1.0"}
_TIMEOUT = 25
_POINT_PAD = 0.02  # ~2 km di bbox attorno al punto quando manca il viewport
_MIN_INTERVAL = 1.1  # intervallo minimo tra richieste Overpass (policy pubblica ~1/s)
_MAX_RETRIES = 2     # retry su rate-limit / risposta non-JSON
_state = {"last": 0.0}  # timestamp dell'ultima richiesta (throttle globale di processo)


def _default_http_post(url, data, headers, timeout):
    import requests
    resp = requests.post(url, data=data, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_street(name: str, bbox, *, http_post=None, sleep=None):
    """Unisce tutti i tratti (way highway) con quel nome nel `bbox` (south, west, north, east)
    in una MultiLineString GeoJSON. Ritorna None se assente/errore/rate-limit.
    Throttle (~1/s) + retry con backoff per resistere al rate-limit di Overpass pubblico.
    `http_post(url, data, headers, timeout) -> json` e `sleep(seconds)` sono iniettabili per i test."""
    post = http_post or _default_http_post
    _sleep = sleep or time.sleep
    s, w, n, e = bbox
    safe = name.replace('"', '\\"')
    query = (f"[out:json][timeout:{_TIMEOUT}];"
             f'(way["name"="{safe}"]["highway"]({s},{w},{n},{e}););out geom;')

    last_exc = None
    for attempt in range(_MAX_RETRIES + 1):
        # Throttle globale: rispetta l'intervallo minimo tra richieste Overpass.
        wait = _MIN_INTERVAL - (time.monotonic() - _state["last"])
        if wait > 0:
            _sleep(wait)
        _state["last"] = time.monotonic()
        try:
            data = post(_OVERPASS_URL, {"data": query}, _HEADERS, _TIMEOUT + 5)
        except Exception as exc:  # noqa: BLE001 - rate-limit/rete/non-JSON: ritenta poi degrada
            last_exc = exc
            if attempt < _MAX_RETRIES:
                _sleep(1.0 * (attempt + 1))  # backoff crescente
            continue
        lines = []
        for el in (data or {}).get("elements", []):
            geom = el.get("geometry")
            if el.get("type") == "way" and geom:
                lines.append([[p["lon"], p["lat"]] for p in geom])
        # Risultato ottenuto (anche vuoto = legittimo): non ritentare.
        return {"type": "MultiLineString", "coordinates": lines} if lines else None

    log.warning("overpass fetch_street('%s') failed after retries: %s", name, last_exc)
    return None


def resolve_place(query: str, viewbox=None, *, geocode_fn=geocode, street_fn=fetch_street):
    """Geocodifica con Nominatim; se il risultato è una STRADA (LineString), ne recupera la
    geometria intera via Overpass. Aree/POI restano come da Nominatim. Fallback a Nominatim.
    Stessa firma/shape di `geocode` -> i tool non cambiano."""
    result = geocode_fn(query, viewbox)
    if result is None:
        return None
    geometry = result.get("geometry") or {}
    if geometry.get("type") == "LineString":
        if viewbox:
            w, n, e, s = viewbox
            bbox = (s, w, n, e)
        else:
            lat, lon = result["lat"], result["lon"]
            bbox = (lat - _POINT_PAD, lon - _POINT_PAD, lat + _POINT_PAD, lon + _POINT_PAD)
        street_name = result["name"].split(",")[0].strip()
        full = street_fn(street_name, bbox)
        if full:
            result = {**result, "geometry": full}
    return result
