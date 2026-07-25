from typing import TypedDict, Annotated, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage

from .prompts import AGENT_SYSTEM_PROMPT, viewport_hint
from .geojson import merge_geojson, geojson_reducer

CLARIFY_TOOL_NAME = "request_clarification"


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    geojson: Annotated[Optional[str], geojson_reducer]
    session_id: str
    viewport: Optional[dict]


def build_graph(*, llm, tools, ground_fn, checkpointer):
    registry = {t.name: t for t in tools}

    def agent_node(state: AgentState):
        bound = llm.bind_tools(tools)
        system = AGENT_SYSTEM_PROMPT + viewport_hint(state.get("viewport"))
        ai = bound.invoke([SystemMessage(content=system)] + state["messages"])
        return {"messages": [ai]}

    def tools_node(state: AgentState):
        last = state["messages"][-1]
        tool_messages = []
        geo = None
        for call in last.tool_calls:
            tool = registry.get(call["name"])
            if tool is None:
                tool_messages.append(ToolMessage(content=f"unknown tool {call['name']}",
                                                 tool_call_id=call["id"]))
                continue
            result = tool.invoke(call["args"])
            tool_messages.append(ToolMessage(content=result["summary"], tool_call_id=call["id"]))
            geo = merge_geojson(geo, result.get("geojson"))
        return {"messages": tool_messages, "geojson": geo}

    def ground_node(state: AgentState):
        last = state["messages"][-1]
        data = "\n".join(m.content for m in state["messages"] if isinstance(m, ToolMessage))
        grounded = ground_fn(last.content, data)
        return {"messages": [AIMessage(content=grounded, id=last.id)]}

    def clarify_node(state: AgentState):
        last = state["messages"][-1]
        question = next((c["args"].get("question", "Chiarimento richiesto.")
                         for c in last.tool_calls if c["name"] == CLARIFY_TOOL_NAME),
                        "Chiarimento richiesto.")
        answer = interrupt({"question": question})
        msgs = []
        for c in last.tool_calls:
            content = answer if c["name"] == CLARIFY_TOOL_NAME else "(in attesa di chiarimento)"
            msgs.append(ToolMessage(content=content, tool_call_id=c["id"]))
        return {"messages": msgs}

    def route_after_agent(state: AgentState):
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None)
        if not calls:
            return "ground"
        if any(c["name"] == CLARIFY_TOOL_NAME for c in calls):
            return "clarify"
        return "tools"

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("ground", ground_node)
    g.add_node("clarify", clarify_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent,
                            {"tools": "tools", "ground": "ground", "clarify": "clarify"})
    g.add_edge("tools", "agent")
    g.add_edge("clarify", "agent")
    g.add_edge("ground", END)
    return g.compile(checkpointer=checkpointer)
