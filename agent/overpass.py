import logging

from .geocode import geocode

log = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "aegis-geoint/1.0"}
_TIMEOUT = 25
_POINT_PAD = 0.02  # ~2 km di bbox attorno al punto quando manca il viewport


def _default_http_post(url, data, headers, timeout):
    import requests
    resp = requests.post(url, data=data, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_street(name: str, bbox, *, http_post=None):
    """Unisce tutti i tratti (way highway) con quel nome nel `bbox` (south, west, north, east)
    in una MultiLineString GeoJSON. Ritorna None se assente/errore/rate-limit.
    `http_post(url, data, headers, timeout) -> json` è iniettabile per i test."""
    post = http_post or _default_http_post
    s, w, n, e = bbox
    safe = name.replace('"', '\\"')
    query = (f"[out:json][timeout:{_TIMEOUT}];"
             f'(way["name"="{safe}"]["highway"]({s},{w},{n},{e}););out geom;')
    try:
        data = post(_OVERPASS_URL, {"data": query}, _HEADERS, _TIMEOUT + 5)
    except Exception as exc:  # noqa: BLE001 - rate-limit/rete/non-JSON: degrada con grazia
        log.warning("overpass fetch_street('%s') failed: %s", name, exc)
        return None
    lines = []
    for el in (data or {}).get("elements", []):
        geom = el.get("geometry")
        if el.get("type") == "way" and geom:
            lines.append([[p["lon"], p["lat"]] for p in geom])
    if not lines:
        return None
    return {"type": "MultiLineString", "coordinates": lines}


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
