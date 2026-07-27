import contextvars
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Viewport corrente dell'operatore (impostato da agent.run prima di graph.invoke,
# letto dai tool locate_place/buffer_around). Evita InjectedState (langgraph.prebuilt).
current_viewport = contextvars.ContextVar("current_viewport", default=None)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "aegis-geoint/1.0"}
_TIMEOUT = 8


def _default_http_get(url, params, headers, timeout):
    import requests
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def extract_viewport_bounds(viewport: Optional[dict]) -> Optional[tuple[float, float, float, float]]:
    """Estrarre (south, west, north, east) da qualsiasi formato viewport dict."""
    if not isinstance(viewport, dict):
        return None

    north = viewport.get("north")
    south = viewport.get("south")
    east = viewport.get("east")
    west = viewport.get("west")

    if any(v is None for v in (north, south, east, west)):
        bounds = viewport.get("bounds")
        if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            try:
                south, west = float(bounds[0][0]), float(bounds[0][1])
                north, east = float(bounds[1][0]), float(bounds[1][1])
            except (ValueError, TypeError, IndexError):
                pass

    if any(v is None for v in (north, south, east, west)):
        lat = viewport.get("lat")
        lon = viewport.get("lon")
        if lat is None or lon is None:
            center = viewport.get("center")
            if isinstance(center, (list, tuple)) and len(center) == 2:
                try:
                    lat, lon = float(center[0]), float(center[1])
                except (ValueError, TypeError):
                    pass
        if lat is not None and lon is not None:
            delta = 0.05
            south, west = lat - delta, lon - delta
            north, east = lat + delta, lon + delta

    if all(v is not None for v in (north, south, east, west)):
        return (float(south), float(west), float(north), float(east))
    return None


def viewbox_from_viewport(viewport: Optional[dict]):
    """Converte il viewport nel viewbox Nominatim (west, north, east, south)."""
    b = extract_viewport_bounds(viewport)
    if not b:
        return None
    south, west, north, east = b
    return (west, north, east, south)


def geocode(query: str, viewbox=None, *, http_get=None) -> Optional[dict]:
    """Risolve un nome in coordinate + geometria reale via Nominatim (polygon_geojson).
    Ritorna {'name','lat','lon','geometry'} sul miglior match, None se assente/errore.
    `geometry` è la GeoJSON di OSM; se assente, fallback a un Point da lat/lon.
    `http_get(url, params, headers, timeout) -> json` è iniettabile per i test."""
    get = http_get or _default_http_get
    params = {"q": query, "format": "jsonv2", "polygon_geojson": 1, "limit": 1}
    if viewbox:
        w, n, e, s = viewbox
        params["viewbox"] = f"{w},{n},{e},{s}"
        params["bounded"] = 0  # preferenza sulla vista, non vincolo rigido
    try:
        data = get(_NOMINATIM_URL, params, _HEADERS, _TIMEOUT)
    except Exception as exc:  # noqa: BLE001 - rete/timeout/policy: degrada con grazia
        log.warning("geocode('%s') failed: %s", query, exc)
        return None
    if not data:
        return None
    top = data[0]
    lat = float(top["lat"])
    lon = float(top["lon"])
    geometry = top.get("geojson") or {"type": "Point", "coordinates": [lon, lat]}
    return {"name": top.get("display_name", query), "lat": lat, "lon": lon, "geometry": geometry}
