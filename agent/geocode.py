import contextvars
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Viewport corrente dell'operatore (impostato da agent.run prima di graph.invoke,
# letto dal tool geocode_place). Evita InjectedState (langgraph.prebuilt, rotto qui).
current_viewport = contextvars.ContextVar("current_viewport", default=None)

_default_geocoder = None


def _get_default_geocoder():
    global _default_geocoder
    if _default_geocoder is None:
        from geopy.geocoders import Nominatim
        _default_geocoder = Nominatim(user_agent="aegis-geoint/1.0", timeout=5)
    return _default_geocoder


def viewbox_from_viewport(viewport: Optional[dict]):
    """Converte il viewport {north,south,east,west} nel viewbox geopy (due angoli lat/lon)."""
    if not viewport:
        return None
    return [(viewport["north"], viewport["east"]), (viewport["south"], viewport["west"])]


def geocode(query: str, viewbox=None, *, geocoder=None) -> Optional[dict]:
    """Risolve un nome di luogo in coordinate reali via Nominatim.
    Ritorna {'name','lat','lon'} sul miglior match, None se assente/errore.
    `geocoder` è iniettabile per i test (nessuna rete)."""
    gc = geocoder or _get_default_geocoder()
    kwargs = {}
    if viewbox:
        kwargs["viewbox"] = viewbox
        kwargs["bounded"] = False  # preferenza sulla vista, non vincolo rigido
    try:
        loc = gc.geocode(query, **kwargs)
    except Exception as exc:  # noqa: BLE001 - rete/timeout/policy: degrada con grazia
        log.warning("geocode('%s') failed: %s", query, exc)
        return None
    if loc is None:
        return None
    return {"name": loc.address, "lat": loc.latitude, "lon": loc.longitude}
