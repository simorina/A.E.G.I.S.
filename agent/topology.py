import json
import logging
from typing import Optional, Union, Dict, Any
import shapely
from shapely.geometry import shape, mapping
from shapely.validation import explain_validity

log = logging.getLogger(__name__)

def repair_geojson(geojson_input: Optional[Union[str, Dict[str, Any]]]) -> Optional[str]:
    """
    GeoJSON Topological Repair Guardrail.
    Inspects input GeoJSON FeatureCollection, validates geometry topology (ST_IsValid equivalent),
    fixes self-intersecting polygons, unclosed rings, or degenerate shapes via shapely.make_valid(),
    and returns a guaranteed valid GeoJSON string.
    """
    if geojson_input is None:
        return None

    if isinstance(geojson_input, str):
        try:
            data = json.loads(geojson_input)
        except Exception as exc:
            log.warning("repair_geojson: Invalid JSON string: %s", exc)
            return None
    elif isinstance(geojson_input, dict):
        data = geojson_input
    else:
        return None

    if not isinstance(data, dict):
        return None

    gtype = data.get("type")
    features = []

    if gtype == "FeatureCollection":
        raw_features = data.get("features", [])
    elif gtype == "Feature":
        raw_features = [data]
    elif "coordinates" in data:
        raw_features = [{"type": "Feature", "geometry": data, "properties": {}}]
    else:
        return None

    repaired_features = []
    for feat in raw_features:
        if not isinstance(feat, dict):
            continue
        geom_dict = feat.get("geometry")
        properties = feat.get("properties", {})

        if not geom_dict:
            # Preserve non-spatial / null-geometry features
            repaired_features.append({
                "type": "Feature",
                "geometry": None,
                "properties": properties
            })
            continue

        try:
            geom = shape(geom_dict)
            if geom.is_empty:
                repaired_features.append({
                    "type": "Feature",
                    "geometry": None,
                    "properties": properties
                })
                continue

            # Topological validation and repair
            if not geom.is_valid:
                log.info("Repairing invalid topology: %s", explain_validity(geom))
                geom = shapely.make_valid(geom)

            # Convert back to dict
            repaired_geom = mapping(geom)
            repaired_features.append({
                "type": "Feature",
                "geometry": repaired_geom,
                "properties": properties
            })
        except Exception as exc:
            log.warning("Skipping unrepairable geometry, preserving feature: %s", exc)
            repaired_features.append({
                "type": "Feature",
                "geometry": None,
                "properties": properties
            })

    if not repaired_features:
        return None

    return json.dumps({
        "type": "FeatureCollection",
        "features": repaired_features
    }, separators=(',', ':'))
