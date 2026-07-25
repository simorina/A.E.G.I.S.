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

def test_spatial_template_injects_schema_and_placeholders():
    t = prompts.spatial_query_template("myschema")
    assert "myschema" in t
    assert "schema1" not in t
    for ph in ("{table_info}", "{question}", "{error}"):
        assert ph in t
    assert "ST_DWithin" in t or "ST_Distance" in t

def test_grounding_template_has_placeholders():
    assert "{draft}" in prompts.GROUNDING_TEMPLATE
    assert "{data}" in prompts.GROUNDING_TEMPLATE

def test_system_prompt_mentions_new_tools():
    p = prompts.AGENT_SYSTEM_PROMPT
    assert "spatial_analysis" in p
    assert "request_clarification" in p
    assert "geocode_place" in p


def test_viewport_hint_present_and_absent():
    assert prompts.viewport_hint(None) == ""
    vp = {"lat": 45.46, "lon": 9.19, "north": 45.5, "south": 45.4, "east": 9.3, "west": 9.1}
    hint = prompts.viewport_hint(vp)
    assert "OPERATOR MAP VIEW" in hint
    assert "45.46" in hint
    assert "9.19" in hint
