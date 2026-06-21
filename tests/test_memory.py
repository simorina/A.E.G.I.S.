from agent.memory import ConversationMemory

def test_append_and_get_in_order():
    m = ConversationMemory(max_turns=6)
    m.append("s1", "user", "ciao")
    m.append("s1", "assistant", "ack")
    assert m.get("s1") == [("user", "ciao"), ("assistant", "ack")]

def test_sessions_are_isolated():
    m = ConversationMemory()
    m.append("a", "user", "x")
    m.append("b", "user", "y")
    assert m.get("a") == [("user", "x")]
    assert m.get("b") == [("user", "y")]

def test_unknown_session_returns_empty():
    assert ConversationMemory().get("nope") == []

def test_cap_keeps_most_recent():
    m = ConversationMemory(max_turns=1)  # cap = 2 messaggi
    m.append("s", "user", "1")
    m.append("s", "assistant", "2")
    m.append("s", "user", "3")
    assert m.get("s") == [("assistant", "2"), ("user", "3")]

def test_clear_removes_session():
    m = ConversationMemory()
    m.append("s", "user", "x")
    m.clear("s")
    assert m.get("s") == []
