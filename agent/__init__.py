"""A.E.G.I.S. agent package: NL->PostGIS tool-calling con guardrail e memoria."""
import asyncio
import logging

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage


from .config import load_config
from .conversations import ensure_schema
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

if engine is not None:
    try:
        ensure_schema(engine, config.schema)
    except Exception as exc:  # noqa: BLE001 - non bloccare l'avvio
        log.error("ensure_schema failed: %s", exc)

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


# Col DB spento i tool SQL ricevono None e degradano puliti (DATABASE_OFFLINE);
# i tool geo (locate/buffer/trace) e la vision restano operativi.
_exec_sql = _execute_sql if engine is not None else None


def _briefing(data_summary):
    return _briefing_chain.invoke({"data_summary": data_summary})


def _analyze_image(image, context="", mime_type="image/jpeg"):
    return analyze_satellite_image(vision_llm, image, context, mime_type)


def _build_tools(ctx):
    return make_tools(
        generate_query_sql=_generate_query_sql,
        generate_geometry_sql=_generate_geometry_sql,
        execute_sql=_exec_sql,
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
    execute_sql=_exec_sql,
    schema=config.schema,
    geocode_fn=resolve_place,
) + [request_clarification]


def build_checkpointer(db_uri):
    """Checkpointer persistente su Postgres; fallback a MemorySaver se non disponibile.

    Usa un ConnectionPool invece di una singola connessione tenuta aperta per la
    vita del processo. Utilizza DualPostgresSaver per garantire compatibilità
    sia con invoke() sincrono che con astream_events() asincrono per SSE.
    """
    if db_uri:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            class DualPostgresSaver(PostgresSaver):
                async def aget_tuple(self, config):
                    return await asyncio.to_thread(self.get_tuple, config)

                async def aput(self, config, checkpoint, metadata, new_versions):
                    return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

                async def aput_writes(self, config, writes, task_id, task_path=None):
                    return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

                async def alist(self, config, *, filter=None, before=None, limit=None):
                    return await asyncio.to_thread(self.list, config, filter=filter, before=before, limit=limit)

            pool = ConnectionPool(
                conninfo=db_uri,
                min_size=1,
                max_size=5,
                open=True,
                check=ConnectionPool.check_connection,   # scarta le connessioni morte
                kwargs={"autocommit": True, "row_factory": dict_row},
            )
            saver = DualPostgresSaver(pool)
            saver.setup()
            return saver, "postgres"
        except Exception as exc:  # noqa: BLE001 - dipendenza assente o DB irraggiungibile
            log.warning("Postgres checkpointer non disponibile (%s); uso MemorySaver", exc)
    return MemorySaver(), "memory"



_checkpointer, _checkpointer_kind = build_checkpointer(config.db_uri if engine is not None else None)
log.info("Checkpointer: %s", _checkpointer_kind)

_graph = build_graph(llm=text_llm, tools=_graph_tools, ground_fn=_ground,
                     checkpointer=_checkpointer)


_orchestrator = Orchestrator(
    llm=text_llm,
    build_tools=_build_tools,
    analyze_image=_analyze_image,
    briefing=_briefing,
    memory=memory,
    use_tools=config.tool_calling,
    router=keyword_router,
)


from .topology import repair_geojson
from .opsec import redact_text
from .evaluator import evaluate_briefing_consistency


def get_state_history(thread_id: str):
    """Retrieve checkpoint history for Time-Travel / State Rewind."""
    cfg = {"configurable": {"thread_id": thread_id}}
    history = []
    try:
        for state in _graph.get_state_history(cfg):
            history.append({
                "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id"),
                "next": state.next,
                "values_keys": list(state.values.keys()) if state.values else []
            })
    except Exception as exc:
        log.warning("get_state_history failed: %s", exc)
    return history


def rewind_checkpoint(thread_id: str, checkpoint_id: str):
    """Rewind graph state to a specific checkpoint_id (Time-Travel)."""
    cfg = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
    try:
        target_state = _graph.get_state(cfg)
        if target_state and target_state.values:
            _graph.update_state({"configurable": {"thread_id": thread_id}}, target_state.values)
            return True
    except Exception as exc:
        log.warning("rewind_checkpoint failed: %s", exc)
    return False


def run(message, session_id, image=None, mime_type="image/jpeg", resume=None,
        viewport=None, conversation_id=None):
    # Nessuna guardia offline a livello di run(): i tool geo/vision funzionano senza DB;
    # i soli tool SQL degradano puliti (DATABASE_OFFLINE) via execute_sql=None.

    # Fallback per modelli senza tool-calling nativo.
    if not config.tool_calling:
        out = _orchestrator.run(message, session_id, image, mime_type)
        return {**out, "awaiting_input": False}

    if image is not None:
        text = _analyze_image(image, message or "", mime_type)
        return {"text": redact_text(text), "geojson": None, "awaiting_input": False}

    thread_id = conversation_id or session_id
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": config.recursion_limit}

    if resume is not None:
        inp = Command(resume=resume)
    else:
        inp = {"messages": [HumanMessage(content=message)], "session_id": thread_id,
               "geojson": RESET_GEOJSON, "viewport": viewport}

    # La vista corrente è disponibile ai tool (geocode_place) per il turno.
    token = current_viewport.set(viewport)
    try:
        result = _graph.invoke(inp, cfg)
    finally:
        current_viewport.reset(token)

    if result.get("__interrupt__"):
        question = result["__interrupt__"][0].value.get("question", "Chiarimento richiesto.")
        return {"text": redact_text(question), "geojson": None, "awaiting_input": True}

    final_text = redact_text(result["messages"][-1].content)
    raw_geojson = result.get("geojson")
    if raw_geojson == RESET_GEOJSON:
        raw_geojson = None

    # Section 4 Guardrails: Topology Repair & Evaluator Metrics
    repaired_geojson = repair_geojson(raw_geojson)
    eval_metrics = evaluate_briefing_consistency(final_text, repaired_geojson)

    return {
        "text": final_text,
        "geojson": repaired_geojson,
        "awaiting_input": False,
        "evaluation": eval_metrics
    }


async def run_stream(message, session_id, image=None, mime_type="image/jpeg", resume=None,
                     viewport=None, conversation_id=None):
    """Generatore asincrono di eventi per SSE: trasmette status, token del briefing e risultato finale."""
    if not config.tool_calling:
        out = await asyncio.to_thread(_orchestrator.run, message, session_id, image, mime_type)
        yield {"type": "status", "content": "Riconoscimento tattico via orchestratore..."}
        yield {"type": "token", "content": out.get("text", "")}
        yield {"type": "final", **out, "awaiting_input": False}
        return

    if image is not None:
        yield {"type": "status", "content": "Analisi ottica satellitare in corso..."}
        text = await asyncio.to_thread(_analyze_image, image, message or "", mime_type)
        redacted = redact_text(text)
        yield {"type": "token", "content": redacted}
        yield {"type": "final", "text": redacted, "geojson": None, "awaiting_input": False}
        return

    thread_id = conversation_id or session_id
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": config.recursion_limit}

    if resume is not None:
        inp = Command(resume=resume)
    else:
        inp = {"messages": [HumanMessage(content=message)], "session_id": thread_id,
               "geojson": RESET_GEOJSON, "viewport": viewport}

    token = current_viewport.set(viewport)
    try:
        stream_success = False
        try:
            yield {"type": "status", "content": "Analisi requisiti tattici & selezione strumenti..."}
            async for event in _graph.astream_events(inp, cfg, version="v2"):
                kind = event.get("event")
                if kind == "on_tool_start":
                    tool_name = event.get("name")
                    yield {"type": "status", "content": f"Esecuzione tool tattico: {tool_name}..."}
                elif kind == "on_tool_end":
                    tool_name = event.get("name")
                    yield {"type": "status", "content": f"Tool {tool_name} completato."}
                elif kind == "on_chat_model_start":
                    yield {"type": "status", "content": "Elaborazione tattica briefing..."}
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and getattr(chunk, "content", None):
                        yield {"type": "token", "content": chunk.content}
            stream_success = True
        except Exception as exc:
            log.warning("astream_events error: %s - Esecuzione via threadpool fallback", exc, exc_info=True)
            yield {"type": "status", "content": "Generazione briefing in corso..."}
            await asyncio.to_thread(_graph.invoke, inp, cfg)

    finally:
        current_viewport.reset(token)

    state = _graph.get_state(cfg)

    interrupt_question = None
    if state:
        if getattr(state, "tasks", None):
            for task in state.tasks:
                interrupts = getattr(task, "interrupts", None)
                if interrupts:
                    for intr in interrupts:
                        val = getattr(intr, "value", None)
                        if isinstance(val, dict) and "question" in val:
                            interrupt_question = val["question"]
                            break
                        elif isinstance(val, str):
                            interrupt_question = val
                            break
                if interrupt_question:
                    break
        if not interrupt_question and isinstance(state.values, dict) and state.values.get("__interrupt__"):
            question = state.values["__interrupt__"][0].value.get("question", "Chiarimento richiesto.")
            interrupt_question = question

    if interrupt_question:
        yield {"type": "final", "text": redact_text(interrupt_question), "geojson": None, "awaiting_input": True}
        return

    if state.values and state.values.get("messages"):
        final_msg = state.values["messages"][-1]
        final_text = redact_text(final_msg.content)
        raw_geojson = state.values.get("geojson")
        if raw_geojson == RESET_GEOJSON:
            raw_geojson = None

        repaired_geojson = repair_geojson(raw_geojson)
        eval_metrics = evaluate_briefing_consistency(final_text, repaired_geojson)

        yield {
            "type": "final",
            "text": final_text,
            "geojson": repaired_geojson,
            "awaiting_input": False,
            "evaluation": eval_metrics
        }
    else:
        yield {"type": "final", "text": "Nessun dato tattico disponibile.", "geojson": None, "awaiting_input": False}


__all__ = [
    "engine", "vision_llm", "config", "run", "run_stream", "analyze_satellite_image",
    "get_state_history", "rewind_checkpoint", "repair_geojson", "redact_text",
    "evaluate_briefing_consistency"
]

