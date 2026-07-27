import pytest
from agent.tools import make_tools, run_sql_pipeline, make_graph_tools


class FakeGDF:
    def __init__(self, empty=False):
        self.empty = empty
    def to_json(self):
        return '{"type":"FeatureCollection","features":[]}'
    def drop(self, columns=None, errors=None):
        return self
    def to_string(self):
        return "name\nDuomo"


def _tools(ctx, gen_q=None, gen_g=None, execute=None, max_attempts=3):
    return {t.name: t for t in make_tools(
        generate_query_sql=gen_q or (lambda request, error: "SELECT 1 AS geom"),
        generate_geometry_sql=gen_g or (lambda request, error: "SELECT 'L' AS label, 1 AS geom"),
        execute_sql=execute or (lambda sql: FakeGDF()),
        schema="schema1",
        ctx=ctx,
        max_attempts=max_attempts,
    )}


def test_query_intel_success_sets_geojson():
    ctx = {"geojson": None}
    tools = _tools(ctx,
                   gen_q=lambda request, error: "SELECT name FROM schema1.fermate_metro",
                   execute=lambda sql: FakeGDF())
    out = tools["query_intel"].invoke({"request": "list metro"})
    assert "Duomo" in out
    assert ctx["geojson"] is not None

def test_query_intel_blocks_unsafe_and_never_executes():
    ctx = {"geojson": None}
    calls = []
    tools = _tools(ctx,
                   gen_q=lambda request, error: "DROP TABLE schema1.parks",
                   execute=lambda sql: calls.append(sql) or FakeGDF())
    out = tools["query_intel"].invoke({"request": "wipe"})
    assert "DENIED" in out
    assert calls == []

def test_query_intel_retries_then_succeeds():
    ctx = {"geojson": None}
    state = {"n": 0}
    def execute(sql):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("syntax error")
        return FakeGDF()
    tools = _tools(ctx,
                   gen_q=lambda request, error: "SELECT name FROM schema1.parks",
                   execute=execute)
    out = tools["query_intel"].invoke({"request": "parks"})
    assert "Duomo" in out
    assert state["n"] == 2

def test_query_intel_empty_result_message():
    ctx = {"geojson": None}
    tools = _tools(ctx, execute=lambda sql: FakeGDF(empty=True))
    out = tools["query_intel"].invoke({"request": "x"})
    assert "No tactical data" in out
    assert ctx["geojson"] is None

def test_draw_geometry_sets_geojson():
    ctx = {"geojson": None}
    tools = _tools(ctx,
                   gen_g=lambda request, error: "SELECT 'AO' AS label, 1 AS geom",
                   execute=lambda sql: FakeGDF())
    out = tools["draw_geometry"].invoke({"request": "draw a zone"})
    assert ctx["geojson"] is not None

def test_run_sql_pipeline_success_returns_dict():
    out = run_sql_pipeline(
        lambda request, error: "SELECT name FROM schema1.parks",
        "parks",
        execute_sql=lambda sql: FakeGDF(),
        schema="schema1",
    )
    assert "Duomo" in out["summary"]
    assert out["geojson"] is not None

def test_run_sql_pipeline_offline_when_execute_sql_none():
    calls = []
    out = run_sql_pipeline(lambda request, error: calls.append(1) or "SELECT 1",
                           "x", execute_sql=None, schema="schema1")
    assert "DATABASE_OFFLINE" in out["summary"]
    assert out["geojson"] is None
    assert calls == []  # non genera nemmeno l'SQL


def test_run_sql_pipeline_blocks_unsafe():
    calls = []
    out = run_sql_pipeline(
        lambda request, error: "DROP TABLE schema1.parks",
        "wipe",
        execute_sql=lambda sql: calls.append(sql) or FakeGDF(),
        schema="schema1",
    )
    assert "DENIED" in out["summary"]
    assert out["geojson"] is None
    assert calls == []

def test_make_graph_tools_names_and_dict_return():
    tools = {t.name: t for t in make_graph_tools(
        generate_query_sql=lambda request, error: "SELECT name FROM schema1.parks",
        generate_geometry_sql=lambda request, error: "SELECT 'L' AS label, 1 AS geom",
        generate_spatial_sql=lambda request, error: "SELECT name FROM schema1.hospitals",
        execute_sql=lambda sql: FakeGDF(),
        schema="schema1",
    )}
    assert set(tools) == {
        "query_intel", "draw_geometry", "spatial_analysis",
        "locate_place", "buffer_around", "trace_streets",
        "spatial_code_interpreter", "analyze_multispectral_band",
        "get_tactical_weather", "calculate_elevation_profile"
    }
    out = tools["spatial_analysis"].invoke({"request": "nearest"})
    assert out["geojson"] is not None
    assert "Duomo" in out["summary"]


def _graph_tools(geocode_fn):
    return {t.name: t for t in make_graph_tools(
        generate_query_sql=lambda request, error: "SELECT 1 AS geom",
        generate_geometry_sql=lambda request, error: "SELECT 1 AS geom",
        generate_spatial_sql=lambda request, error: "SELECT 1 AS geom",
        execute_sql=lambda sql: FakeGDF(),
        schema="schema1",
        geocode_fn=geocode_fn,
    )}


_LINE = {"type": "LineString", "coordinates": [[9.195, 45.468], [9.197, 45.466]]}
_POINT = {"type": "Point", "coordinates": [11.877, 45.398]}


def test_locate_place_returns_real_geometry():
    import json
    tools = _graph_tools(lambda place, viewbox=None: {
        "name": "Via Monte Napoleone", "lat": 45.467, "lon": 9.196, "geometry": _LINE})
    out = tools["locate_place"].invoke({"place": "Via Monte Napoleone"})
    assert "LOCATED" in out["summary"]
    fc = json.loads(out["geojson"])
    assert fc["features"][0]["geometry"] == _LINE


def test_buffer_around_returns_polygon():
    import json
    tools = _graph_tools(lambda place, viewbox=None: {
        "name": "Prato della Valle", "lat": 45.398, "lon": 11.877, "geometry": _POINT})
    out = tools["buffer_around"].invoke({"place": "Prato della Valle", "radius_m": 300})
    assert "BUFFER" in out["summary"] and "300" in out["summary"]
    geom = json.loads(out["geojson"])["features"][0]["geometry"]
    assert geom["type"] in ("Polygon", "MultiPolygon")


def test_locate_place_geocode_failure():
    tools = _graph_tools(lambda place, viewbox=None: None)
    out = tools["locate_place"].invoke({"place": "nessun luogo"})
    assert "GEOCODE_FAILED" in out["summary"]
    assert out["geojson"] is None


def _street_tools(fetch_streets_fn):
    return {t.name: t for t in make_graph_tools(
        generate_query_sql=lambda request, error: "SELECT 1 AS geom",
        generate_geometry_sql=lambda request, error: "SELECT 1 AS geom",
        generate_spatial_sql=lambda request, error: "SELECT 1 AS geom",
        execute_sql=lambda sql: FakeGDF(),
        schema="schema1",
        fetch_streets_fn=fetch_streets_fn,
    )}


_VP = {"lat": 45.46, "lon": 9.19, "north": 45.5, "south": 45.4, "east": 9.3, "west": 9.1}
_MLS_A = {"type": "MultiLineString", "coordinates": [[[9.0, 45.0], [9.1, 45.1]]]}
_MLS_B = {"type": "MultiLineString", "coordinates": [[[9.2, 45.2], [9.3, 45.3]]]}


def test_trace_streets_multiple_in_one_call():
    import json
    from agent.geocode import current_viewport
    seen = {}

    def fake(names, bbox):
        seen["names"] = names
        seen["bbox"] = bbox
        return {"Via A": _MLS_A, "Via B": _MLS_B}

    token = current_viewport.set(_VP)
    try:
        tools = _street_tools(fake)
        out = tools["trace_streets"].invoke({"places": ["Via A", "Via B"]})
    finally:
        current_viewport.reset(token)
    assert "TRACED" in out["summary"] and "2" in out["summary"]
    fc = json.loads(out["geojson"])
    assert len(fc["features"]) == 2
    assert seen["names"] == ["Via A", "Via B"]
    assert seen["bbox"] == (45.4, 9.1, 45.5, 9.3)  # (s,w,n,e) dal viewport


def test_trace_streets_requires_viewport():
    from agent.geocode import current_viewport
    token = current_viewport.set(None)
    try:
        tools = _street_tools(lambda names, bbox: {"Via A": _MLS_A})
        out = tools["trace_streets"].invoke({"places": ["Via A"]})
    finally:
        current_viewport.reset(token)
    assert out["geojson"] is None


def test_trace_streets_none_found():
    from agent.geocode import current_viewport
    token = current_viewport.set(_VP)
    try:
        tools = _street_tools(lambda names, bbox: {})
        out = tools["trace_streets"].invoke({"places": ["Nope"]})
    finally:
        current_viewport.reset(token)
    assert "GEOCODE_FAILED" in out["summary"]
    assert out["geojson"] is None
