import json
from typing import Optional


def merge_geojson(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Unisce due FeatureCollection GeoJSON (stringhe). Tollera None e JSON invalido."""
    if a is None:
        return b
    if b is None:
        return a
    try:
        fa = json.loads(a)
        fb = json.loads(b)
    except (ValueError, TypeError):
        # Se uno dei due non è JSON valido, preferisci quello valido (a ha priorità).
        try:
            json.loads(a)
            return a
        except (ValueError, TypeError):
            return b
    features = (fa.get("features", []) or []) + (fb.get("features", []) or [])
    return json.dumps({"type": "FeatureCollection", "features": features})
