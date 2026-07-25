from agent import prompts

def test_sql_template_injects_schema():
    t = prompts.sql_query_template("myschema")
    assert "myschema" in t
    assert "schema1" not in t  # nessun hardcode residuo
    for ph in ("{table_info}", "{question}", "{error}"):
        assert ph in t

def test_geometry_template_has_placeholders():
    assert "{request}" in prompts.GEOMETRY_TEMPLATE
    assert "{error}" in prompts.GEOMETRY_TEMPLATE
    assert "ST_" in prompts.GEOMETRY_TEMPLATE  # parla di costruttori PostGIS

def test_briefing_template_has_placeholder():
    assert "{data_summary}" in prompts.BRIEFING_TEMPLATE

def test_system_prompt_mentions_tools_and_geom():
    p = prompts.AGENT_SYSTEM_PROMPT.lower()
    assert "geom" in p
    assert "4326" in prompts.AGENT_SYSTEM_PROMPT
