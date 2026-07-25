from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph


FC1 = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"n":1},"geometry":null}]}'


@tool
def fake_query(request: str) -> dict:
    """query existing intel"""
    return {"summary": "ROWS: Duomo", "geojson": FC1}


class ScriptedLLM:
    """Ritorna in sequenza gli AIMessage predefiniti a ogni invoke."""
    def __init__(self, scripted):
        self._scripted = scripted
        self._i = 0
    def bind_tools(self, tools):
        return self
    def invoke(self, messages):
        ai = self._scripted[self._i]
        self._i += 1
        return ai


def _cfg(tid="t1"):
    return {"configurable": {"thread_id": tid}, "recursion_limit": 12}


def test_multi_step_then_final_and_geojson():
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "fake_query", "args": {"request": "metro"}, "id": "c1"}]),
        AIMessage(content="draft briefing"),  # nessun tool_call -> ground -> END
    ]
    graph = build_graph(llm=ScriptedLLM(scripted), tools=[fake_query],
                        ground_fn=lambda draft, data: draft.upper(), checkpointer=MemorySaver())
    out = graph.invoke({"messages": [("user", "list metro")], "geojson": None, "session_id": "t1"}, _cfg())
    assert out["messages"][-1].content == "DRAFT BRIEFING"   # grounding applicato
    assert out["geojson"] == FC1

def test_grounding_receives_tool_data():
    seen = {}
    def ground(draft, data):
        seen["data"] = data
        return draft
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "fake_query", "args": {"request": "x"}, "id": "c1"}]),
        AIMessage(content="final"),
    ]
    graph = build_graph(llm=ScriptedLLM(scripted), tools=[fake_query],
                        ground_fn=ground, checkpointer=MemorySaver())
    graph.invoke({"messages": [("user", "q")], "geojson": None, "session_id": "t2"}, _cfg("t2"))
    assert "Duomo" in seen["data"]
