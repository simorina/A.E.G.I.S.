import pytest

from agent.conversations import DEFAULT_TITLE, derive_title


def test_derive_title_uses_first_line():
    assert derive_title("traccia via dante\nseconda riga") == "traccia via dante"


def test_derive_title_truncates_with_ellipsis():
    long = "traccia tutte le vie principali del centro storico di milano"
    out = derive_title(long, max_len=20)
    assert len(out) <= 21          # 20 caratteri + ellissi
    assert out.endswith("…")


def test_derive_title_normalises_whitespace():
    assert derive_title("   traccia    via   dante   ") == "traccia via dante"


def test_derive_title_empty_falls_back_to_default():
    assert derive_title("") == DEFAULT_TITLE
    assert derive_title("   \n  ") == DEFAULT_TITLE


@pytest.fixture(scope="module")
def db():
    """Engine reale se il DB è raggiungibile, altrimenti skip dei test CRUD."""
    import agent
    from agent.conversations import ensure_schema
    if agent.engine is None:
        pytest.skip("DB non raggiungibile: test CRUD saltati")
    ensure_schema(agent.engine, agent.config.schema)
    return agent.engine, agent.config.schema


def test_delete_all_removes_only_that_operator(db):
    from agent.conversations import (create_conversation, list_conversations,
                                     append_message, get_messages, delete_all_conversations,
                                     delete_conversation)
    engine, schema = db
    mine_a = create_conversation(engine, schema, "TEST_BULK_OP")
    mine_b = create_conversation(engine, schema, "TEST_BULK_OP")
    append_message(engine, schema, mine_a["id"], "user", "ciao")
    other = create_conversation(engine, schema, "TEST_OTHER_OP")
    try:
        removed = delete_all_conversations(engine, schema, "TEST_BULK_OP")
        assert removed == 2
        assert list_conversations(engine, schema, "TEST_BULK_OP") == []
        assert get_messages(engine, schema, mine_a["id"]) == []          # cascade
        assert len(list_conversations(engine, schema, "TEST_OTHER_OP")) == 1  # non tocca gli altri
        assert delete_all_conversations(engine, schema, "TEST_BULK_OP") == 0  # idempotente
    finally:
        delete_conversation(engine, schema, other["id"])


def test_crud_roundtrip(db):
    from agent.conversations import (create_conversation, list_conversations, get_messages,
                                     append_message, rename_conversation, delete_conversation)
    engine, schema = db
    conv = create_conversation(engine, schema, "TEST_OP")
    assert conv["title"] == DEFAULT_TITLE

    append_message(engine, schema, conv["id"], "user", "ciao")
    append_message(engine, schema, conv["id"], "assistant", "briefing", geojson='{"a":1}')
    msgs = get_messages(engine, schema, conv["id"])
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["geojson"] == '{"a":1}'

    assert rename_conversation(engine, schema, conv["id"], "MISSIONE ALFA") is True
    titles = {c["id"]: c["title"] for c in list_conversations(engine, schema, "TEST_OP")}
    assert titles[conv["id"]] == "MISSIONE ALFA"

    assert delete_conversation(engine, schema, conv["id"]) is True
    assert conv["id"] not in {c["id"] for c in list_conversations(engine, schema, "TEST_OP")}
    assert get_messages(engine, schema, conv["id"]) == []   # cascade
