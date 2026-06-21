from agent.db import readonly_preamble

def test_preamble_sets_timeout_and_readonly():
    stmts = readonly_preamble(5000)
    assert "SET statement_timeout = 5000" in stmts
    assert "SET default_transaction_read_only = on" in stmts

def test_preamble_coerces_to_int():
    # Difesa: niente iniezione tramite timeout non numerico.
    stmts = readonly_preamble(1234)
    assert any("1234" in s for s in stmts)
    assert all(";" not in s for s in stmts)
