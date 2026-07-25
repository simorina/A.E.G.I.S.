import json
from agent.geojson import merge_geojson

FC_A = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"n":"A"},"geometry":null}]}'
FC_B = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"n":"B"},"geometry":null}]}'

def test_merge_none_cases():
    assert merge_geojson(None, None) is None
    assert merge_geojson(FC_A, None) == FC_A
    assert merge_geojson(None, FC_B) == FC_B

def test_merge_concatenates_features():
    merged = json.loads(merge_geojson(FC_A, FC_B))
    names = [f["properties"]["n"] for f in merged["features"]]
    assert names == ["A", "B"]
    assert merged["type"] == "FeatureCollection"

def test_merge_invalid_prefers_valid():
    assert merge_geojson("not-json", FC_B) == FC_B
    assert merge_geojson(FC_A, "not-json") == FC_A
