from langgraph.checkpoint.memory import MemorySaver

import agent


def test_build_checkpointer_memory_when_no_db():
    saver, kind = agent.build_checkpointer(None)
    assert kind == "memory"
    assert isinstance(saver, MemorySaver)


def test_build_checkpointer_memory_on_bad_uri():
    """URI non valido: nessuna eccezione, fallback a memoria."""
    saver, kind = agent.build_checkpointer("postgresql://nobody@127.0.0.1:1/none")
    assert kind == "memory"
    assert isinstance(saver, MemorySaver)
