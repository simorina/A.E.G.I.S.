import json
from agent.geometry import feature_collection, feature_collection_multi, buffer_geometry

LINE = {"type": "LineString", "coordinates": [[9.195, 45.468], [9.197, 45.466]]}
POINT = {"type": "Point", "coordinates": [9.19, 45.46]}


def test_feature_collection_wraps_geometry_with_label():
    fc = json.loads(feature_collection(LINE, "Via Monte Napoleone"))
    assert fc["type"] == "FeatureCollection"
    feat = fc["features"][0]
    assert feat["geometry"] == LINE
    assert feat["properties"]["label"] == "Via Monte Napoleone"


def test_feature_collection_multi_wraps_many():
    fc = json.loads(feature_collection_multi([(LINE, "Via A"), (POINT, "Piazza B")]))
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2
    labels = [f["properties"]["label"] for f in fc["features"]]
    assert labels == ["Via A", "Piazza B"]
    assert fc["features"][0]["geometry"] == LINE


def test_buffer_geometry_of_point_is_polygon():
    fc = json.loads(buffer_geometry(POINT, 500))
    geom = fc["features"][0]["geometry"]
    assert geom["type"] in ("Polygon", "MultiPolygon")
    # un buffer di 500 m produce un anello con molti vertici attorno al punto
    ring = geom["coordinates"][0]
    assert len(ring) > 8


def test_buffer_geometry_expands_bounds():
    # il buffer deve estendersi oltre il punto originale (in lon e lat)
    fc = json.loads(buffer_geometry(POINT, 500))
    ring = fc["features"][0]["geometry"]["coordinates"][0]
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    assert min(lons) < 9.19 < max(lons)
    assert min(lats) < 45.46 < max(lats)
