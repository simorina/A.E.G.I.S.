import json
from typing import Optional


def _parse_fc(s):
    if s is None:
        return None
    try:
        value = json.loads(s)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


from .topology import repair_geojson


def merge_geojson(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Unisce e ripara due FeatureCollection GeoJSON (stringhe). Tollera None, JSON invalido e non-oggetti."""
    fa = _parse_fc(a)
    fb = _parse_fc(b)
    if fa is None and fb is None:
        return None
    if fa is None:
        return b
    if fb is None:
        return a
    features = (fa.get("features") or []) + (fb.get("features") or [])
    merged = json.dumps({"type": "FeatureCollection", "features": features}, separators=(',', ':'))
    return repair_geojson(merged)


RESET_GEOJSON = "__RESET_GEOJSON__"


def geojson_reducer(current, update):
    """Reducer di stato: RESET_GEOJSON azzera l'accumulo (turno nuovo); altrimenti fonde.

    `current` viene normalizzato perche' al PRIMO turno di un thread nuovo il canale
    non ha ancora un valore: LangGraph non invoca il reducer e scrive il sentinella
    tale e quale, che finirebbe nella risposta HTTP (il frontend farebbe
    JSON.parse('__RESET_GEOJSON__') -> eccezione).
    """
    if update == RESET_GEOJSON:
        return None
    if current == RESET_GEOJSON:
        current = None
    return merge_geojson(current, update)
