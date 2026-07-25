import logging
import re

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .prompts import AGENT_SYSTEM_PROMPT

log = logging.getLogger(__name__)

_DRAW_HINTS = re.compile(
    r"\b(draw|create|mark|trace|define|perimeter|zone|corridor|route|buffer|"
    r"area of operations|radius)\b",
    re.IGNORECASE,
)


def keyword_router(message: str) -> str:
    """Fallback senza tool-calling nativo: sceglie il tool per parole chiave."""
    return "draw_geometry" if _DRAW_HINTS.search(message or "") else "query_intel"


class Orchestrator:
    def __init__(self, *, llm, build_tools, analyze_image, briefing, memory,
                 use_tools, router):
        self._llm = llm
        self._build_tools = build_tools
        self._analyze_image = analyze_image
        self._briefing = briefing
        self._memory = memory
        self._use_tools = use_tools
        self._router = router

    def run(self, message, session_id, image=None, mime_type="image/jpeg"):
        ctx = {"geojson": None}

        if image is not None:
            text = self._analyze_image(image, message or "", mime_type)
            self._record(session_id, message or "[IMAGE]", text)
            return {"text": text, "geojson": None}

        tools = self._build_tools(ctx)
        history = self._memory.get(session_id)

        if self._use_tools:
            text = self._run_tool_calling(message, history, tools)
        else:
            text = self._run_router(message, tools)

        self._record(session_id, message, text)
        return {"text": text, "geojson": ctx["geojson"]}

    # --- internals ---

    def _messages(self, history, message):
        msgs = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]
        for role, content in history:
            msgs.append(HumanMessage(content=content) if role == "user"
                        else AIMessage(content=content))
        msgs.append(HumanMessage(content=message))
        return msgs

    def _run_tool_calling(self, message, history, tools):
        registry = {t.name: t for t in tools}
        bound = self._llm.bind_tools(tools)
        ai = bound.invoke(self._messages(history, message))

        outputs = []
        for call in (getattr(ai, "tool_calls", None) or []):
            tool = registry.get(call["name"])
            if tool is None:
                continue
            outputs.append(tool.invoke(call["args"]))

        if not outputs:
            return ai.content or "No actionable intel."
        return self._briefing("\n".join(outputs))

    def _run_router(self, message, tools):
        registry = {t.name: t for t in tools}
        name = self._router(message)
        tool = registry.get(name) or registry["query_intel"]
        output = tool.invoke({"request": message})
        return self._briefing(output)

    def _record(self, session_id, user_msg, assistant_msg):
        self._memory.append(session_id, "user", user_msg)
        self._memory.append(session_id, "assistant", assistant_msg)
