import pytest
from agent.tools import make_tools


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
