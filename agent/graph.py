from typing import TypedDict, Annotated, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage

from .prompts import AGENT_SYSTEM_PROMPT
from .geojson import merge_geojson


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    geojson: Annotated[Optional[str], merge_geojson]
    session_id: str


def build_graph(*, llm, tools, ground_fn, checkpointer):
    registry = {t.name: t for t in tools}

    def agent_node(state: AgentState):
        bound = llm.bind_tools(tools)
        ai = bound.invoke([SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state["messages"])
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

    def route_after_agent(state: AgentState):
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "ground"

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("ground", ground_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "ground": "ground"})
    g.add_edge("tools", "agent")
    g.add_edge("ground", END)
    return g.compile(checkpointer=checkpointer)
