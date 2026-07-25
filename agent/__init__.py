"""A.E.G.I.S. agent package: NL->PostGIS tool-calling con guardrail e memoria."""
import logging

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage

from .config import load_config
from .db import make_engine, make_sql_database, get_table_info, execute_readonly
from .geojson import RESET_GEOJSON
from .geocode import current_viewport
from .overpass import resolve_place
from .llm import build_text_llm, build_vision_llm
from .prompts import (sql_query_template, GEOMETRY_TEMPLATE, BRIEFING_TEMPLATE,
                      spatial_query_template, GROUNDING_TEMPLATE)
from .memory import ConversationMemory
from .tools import make_tools, make_graph_tools, request_clarification
from .vision import analyze_satellite_image
from .orchestrator import Orchestrator, keyword_router
from .graph import build_graph

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agent")

load_dotenv()
config = load_config()

text_llm = build_text_llm(config)
vision_llm = build_vision_llm(config)
memory = ConversationMemory(config.memory_turns)

# DB: degrada con grazia se offline (engine=None).
try:
    engine = make_engine(config.db_uri)
    _sql_db = make_sql_database(config.db_uri, config.schema)
    _table_info = get_table_info(_sql_db)
    log.info("DB connected. Schema: %s", config.schema)
except Exception as exc:  # noqa: BLE001
    log.error("DB init failed: %s", exc)
    engine = None
    _table_info = ""

_query_chain = (ChatPromptTemplate.from_template(sql_query_template(config.schema))
                | text_llm | StrOutputParser())
_geometry_chain = (ChatPromptTemplate.from_template(GEOMETRY_TEMPLATE)
                   | text_llm | StrOutputParser())
_briefing_chain = (ChatPromptTemplate.from_template(BRIEFING_TEMPLATE)
                   | text_llm | StrOutputParser())


def _generate_query_sql(request, error=""):
    return _query_chain.invoke({"table_info": _table_info, "question": request, "error": error})


def _generate_geometry_sql(request, error=""):
    return _geometry_chain.invoke({"request": request, "error": error})


def _execute_sql(sql):
    return execute_readonly(engine, sql, config.statement_timeout_ms)


def _briefing(data_summary):
    return _briefing_chain.invoke({"data_summary": data_summary})


def _analyze_image(image, context="", mime_type="image/jpeg"):
    return analyze_satellite_image(vision_llm, image, context, mime_type)


def _build_tools(ctx):
    return make_tools(
        generate_query_sql=_generate_query_sql,
        generate_geometry_sql=_generate_geometry_sql,
        execute_sql=_execute_sql,
        schema=config.schema,
        ctx=ctx,
    )


_spatial_chain = (ChatPromptTemplate.from_template(spatial_query_template(config.schema))
                  | text_llm | StrOutputParser())
_grounding_chain = (ChatPromptTemplate.from_template(GROUNDING_TEMPLATE)
                    | text_llm | StrOutputParser())


def _generate_spatial_sql(request, error=""):
    return _spatial_chain.invoke({"table_info": _table_info, "question": request, "error": error})


def _ground(draft, data):
    if not data.strip():
        return draft
    return _grounding_chain.invoke({"draft": draft, "data": data})


_graph_tools = make_graph_tools(
    generate_query_sql=_generate_query_sql,
    generate_geometry_sql=_generate_geometry_sql,
    generate_spatial_sql=_generate_spatial_sql,
    execute_sql=_execute_sql,
    schema=config.schema,
    geocode_fn=resolve_place,
) + [request_clarification]

_graph = build_graph(llm=text_llm, tools=_graph_tools, ground_fn=_ground,
                     checkpointer=MemorySaver())


_orchestrator = Orchestrator(
    llm=text_llm,
    build_tools=_build_tools,
    analyze_image=_analyze_image,
    briefing=_briefing,
    memory=memory,
    use_tools=config.tool_calling,
    router=keyword_router,
)


def run(message, session_id, image=None, mime_type="image/jpeg", resume=None, viewport=None):
    if engine is None and image is None:
        return {"text": "Tactical engine offline.", "geojson": None, "awaiting_input": False}

    # Fallback per modelli senza tool-calling nativo.
    if not config.tool_calling:
        out = _orchestrator.run(message, session_id, image, mime_type)
        return {**out, "awaiting_input": False}

    if image is not None:
        text = _analyze_image(image, message or "", mime_type)
        return {"text": text, "geojson": None, "awaiting_input": False}

    cfg = {"configurable": {"thread_id": session_id}, "recursion_limit": config.recursion_limit}

    if resume is not None:
        inp = Command(resume=resume)
    else:
        inp = {"messages": [HumanMessage(content=message)], "session_id": session_id,
               "geojson": RESET_GEOJSON, "viewport": viewport}

    # La vista corrente è disponibile ai tool (geocode_place) per il turno.
    token = current_viewport.set(viewport)
    try:
        result = _graph.invoke(inp, cfg)
    finally:
        current_viewport.reset(token)

    if result.get("__interrupt__"):
        question = result["__interrupt__"][0].value.get("question", "Chiarimento richiesto.")
        return {"text": question, "geojson": None, "awaiting_input": True}

    final = result["messages"][-1].content
    return {"text": final, "geojson": result.get("geojson"), "awaiting_input": False}


__all__ = ["engine", "vision_llm", "config", "run", "analyze_satellite_image"]
