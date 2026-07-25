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


def _escape(name: str) -> str:
    return name.replace('"', '\\"')


def _overpass_request(query, post, _sleep):
    """Esegue una query Overpass con throttle (~1/s) + retry con backoff. None su fallimento."""
    last_exc = None
    for attempt in range(_MAX_RETRIES + 1):
        wait = _MIN_INTERVAL - (time.monotonic() - _state["last"])
        if wait > 0:
            _sleep(wait)
        _state["last"] = time.monotonic()
        try:
            return post(_OVERPASS_URL, {"data": query}, _HEADERS, _TIMEOUT + 5)
        except Exception as exc:  # noqa: BLE001 - rate-limit/rete/non-JSON: ritenta poi degrada
            last_exc = exc
            if attempt < _MAX_RETRIES:
                _sleep(1.0 * (attempt + 1))  # backoff crescente
    log.warning("overpass request failed after retries: %s", last_exc)
    return None


def _ways_by_name(data):
    """Raggruppa i tratti (way) per `tags.name` -> {name: [linee]}."""
    byname = {}
    for el in (data or {}).get("elements", []):
        geom = el.get("geometry")
        if el.get("type") == "way" and geom:
            nm = el.get("tags", {}).get("name")
            byname.setdefault(nm, []).append([[p["lon"], p["lat"]] for p in geom])
    return byname


def bbox_from_viewport(viewport):
    """Bbox Overpass (south, west, north, east) dal viewport, o None."""
    if not viewport:
        return None
    return (viewport["south"], viewport["west"], viewport["north"], viewport["east"])


def fetch_street(name: str, bbox, *, http_post=None, sleep=None):
    """Unisce tutti i tratti (way highway) con quel nome nel `bbox` (south, west, north, east)
    in una MultiLineString GeoJSON. None se assente/errore/rate-limit."""
    s, w, n, e = bbox
    query = (f"[out:json][timeout:{_TIMEOUT}];"
             f'(way["name"="{_escape(name)}"]["highway"]({s},{w},{n},{e}););out geom;')
    data = _overpass_request(query, http_post or _default_http_post, sleep or time.sleep)
    lines = [line for lines in _ways_by_name(data).values() for line in lines]
    return {"type": "MultiLineString", "coordinates": lines} if lines else None


def fetch_streets(names, bbox, *, http_post=None, sleep=None):
    """Traccia PIÙ vie in UNA sola query Overpass (niente rate-limit). Ritorna
    {name: MultiLineString} per le vie trovate nel `bbox` (south, west, north, east)."""
    s, w, n, e = bbox
    union = "".join(f'way["name"="{_escape(nm)}"]["highway"]({s},{w},{n},{e});' for nm in names)
    query = f"[out:json][timeout:{_TIMEOUT}];({union});out geom;"
    data = _overpass_request(query, http_post or _default_http_post, sleep or time.sleep)
    return {nm: {"type": "MultiLineString", "coordinates": lines}
            for nm, lines in _ways_by_name(data).items() if nm}


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
