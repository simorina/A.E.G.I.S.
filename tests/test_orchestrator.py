from agent.orchestrator import Orchestrator, keyword_router
from agent.memory import ConversationMemory


# --- keyword_router ---

def test_router_picks_draw_for_shape_verbs():
    assert keyword_router("draw a patrol perimeter around the duomo") == "draw_geometry"
    assert keyword_router("trace a route to Linate") == "draw_geometry"

def test_router_defaults_to_query():
    assert keyword_router("list all metro stations on M4") == "query_intel"


# --- fakes ---

class FakeTool:
    def __init__(self, name, ctx, geojson='{"gj":1}', text="ROWS"):
        self.name = name
        self._ctx = ctx
        self._geojson = geojson
        self._text = text
    def invoke(self, args):
        self._ctx["geojson"] = self._geojson
        return self._text

class FakeAI:
    def __init__(self, tool_calls=None, content=""):
        self.tool_calls = tool_calls or []
        self.content = content

class FakeBound:
    def __init__(self, ai):
        self._ai = ai
    def invoke(self, messages):
        return self._ai

class FakeLLM:
    def __init__(self, ai):
        self._ai = ai
    def bind_tools(self, tools):
        return FakeBound(self._ai)


def _orch(llm=None, use_tools=True, ctx_holder=None, briefing=None, analyze=None):
    def build_tools(ctx):
        if ctx_holder is not None:
            ctx_holder["ctx"] = ctx
        return [FakeTool("query_intel", ctx), FakeTool("draw_geometry", ctx)]
    return Orchestrator(
        llm=llm,
        build_tools=build_tools,
        analyze_image=analyze or (lambda image, context, mime_type: "RECON"),
        briefing=briefing or (lambda data: f"BRIEF[{data}]"),
        memory=ConversationMemory(),
        use_tools=use_tools,
        router=keyword_router,
    )


def test_image_path_bypasses_tools():
    orch = _orch(use_tools=True)
    out = orch.run("look here", "s1", image=b"IMG", mime_type="image/png")
    assert out["text"] == "RECON"
    assert out["geojson"] is None

def test_tool_calling_path_briefs_and_surfaces_geojson():
    ai = FakeAI(tool_calls=[{"name": "query_intel", "args": {"request": "metro"}}])
    orch = _orch(llm=FakeLLM(ai))
    out = orch.run("list metro", "s1")
    assert out["text"] == "BRIEF[ROWS]"
    assert out["geojson"] == '{"gj":1}'

def test_tool_calling_no_call_returns_model_content():
    ai = FakeAI(tool_calls=[], content="no actionable intel")
    orch = _orch(llm=FakeLLM(ai))
    out = orch.run("hello", "s1")
    assert out["text"] == "no actionable intel"
    assert out["geojson"] is None

def test_router_path_used_when_tools_disabled():
    orch = _orch(use_tools=False)
    out = orch.run("draw a perimeter", "s1")
    assert out["text"] == "BRIEF[ROWS]"
    assert out["geojson"] == '{"gj":1}'

def test_memory_is_recorded():
    ai = FakeAI(tool_calls=[{"name": "query_intel", "args": {"request": "metro"}}])
    mem = ConversationMemory()
    orch = Orchestrator(
        llm=FakeLLM(ai),
        build_tools=lambda ctx: [FakeTool("query_intel", ctx)],
        analyze_image=lambda image, context, mime_type: "RECON",
        briefing=lambda data: "BRIEF",
        memory=mem,
        use_tools=True,
        router=keyword_router,
    )
    orch.run("list metro", "s1")
    assert mem.get("s1") == [("user", "list metro"), ("assistant", "BRIEF")]
