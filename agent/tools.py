import logging

from langchain_core.tools import tool

from .safety import extract_sql, validate_readonly_sql, UnsafeQueryError
from .geocode import geocode, current_viewport, viewbox_from_viewport

log = logging.getLogger(__name__)


@tool
def request_clarification(question: str) -> dict:
    """Ask the operator ONE clarifying question when the request is ambiguous or missing
    required details (which metro line? which coordinates?). Call this ALONE."""
    return {"summary": question, "geojson": None}


def run_sql_pipeline(generate, request, *, execute_sql, schema, max_attempts=3, label: str = "") -> dict:
    """genera->estrai->valida->esegui->auto-correggi. Ritorna {'summary','geojson'}."""
    error = ""
    for attempt in range(max_attempts):
        raw = generate(request=request, error=error)
        sql = extract_sql(raw)
        if not sql:
            error = "the generated query was empty"
            continue
        try:
            validate_readonly_sql(sql, schema)
        except UnsafeQueryError as exc:
            log.warning("%s blocked unsafe SQL: %s", label, exc)
            return {"summary": f"REQUEST_DENIED: unsafe query blocked ({exc}).", "geojson": None}
        try:
            gdf = execute_sql(sql)
        except Exception as exc:  # noqa: BLE001 - errore re-immesso nell'LLM
            error = str(exc)
            log.warning("%s attempt %d failed: %s", label, attempt + 1, exc)
            continue
        if gdf.empty:
            return {"summary": "No tactical data found in this sector.", "geojson": None}
        return {
            "summary": gdf.drop(columns=["geom", "geometry"], errors="ignore").to_string(),
            "geojson": gdf.to_json(),
        }
    return {"summary": f"SYSTEM_FAILURE: {error}", "geojson": None}


def make_graph_tools(*, generate_query_sql, generate_geometry_sql, generate_spatial_sql,
                     execute_sql, schema, geocode_fn=None, max_attempts=3):
    """Tool per il grafo LangGraph: ognuno ritorna {'summary','geojson'}."""
    _geocode = geocode_fn or geocode

    @tool
    def query_intel(request: str) -> dict:
        """Search EXISTING intel already in the database: find, locate, list, count or
        analyze metro stations, parks, hospitals and infrastructure in Milan."""
        return run_sql_pipeline(generate_query_sql, request,
                                execute_sql=execute_sql, schema=schema, max_attempts=max_attempts,
                                label="query_intel")

    @tool
    def draw_geometry(request: str) -> dict:
        """Synthesize a NEW geometry on the map (patrol zone, perimeter, area of operations,
        corridor, route, security buffer) from coordinates or a description. Does NOT read the DB."""
        return run_sql_pipeline(generate_geometry_sql, request,
                                execute_sql=execute_sql, schema=schema, max_attempts=max_attempts,
                                label="draw_geometry")

    @tool
    def spatial_analysis(request: str) -> dict:
        """DERIVED spatial analysis over existing data: distance, nearest neighbour, within a
        radius, intersection (ST_Distance, ST_DWithin, ST_Intersects, KNN)."""
        return run_sql_pipeline(generate_spatial_sql, request,
                                execute_sql=execute_sql, schema=schema, max_attempts=max_attempts,
                                label="spatial_analysis")

    @tool
    def geocode_place(place: str) -> dict:
        """Resolve a NAMED place (square, street, monument, address) to real WGS84
        coordinates. ALWAYS call this before draw_geometry for a named location, then pass
        the returned lat/lon to draw_geometry. Do NOT guess coordinates."""
        result = _geocode(place, viewbox=viewbox_from_viewport(current_viewport.get()))
        if result is None:
            return {"summary": f"GEOCODE_FAILED: '{place}' non trovato. "
                               f"Chiedi conferma delle coordinate all'operatore.", "geojson": None}
        return {"summary": f"GEOCODED: {result['name']} -> "
                          f"lat={result['lat']}, lon={result['lon']}", "geojson": None}

    return [query_intel, draw_geometry, spatial_analysis, geocode_place]


def make_tools(*, generate_query_sql, generate_geometry_sql, execute_sql,
               schema, ctx, max_attempts=3):
    """Legacy (fallback orchestrator): scrive il GeoJSON in ctx['geojson'] e ritorna una stringa."""

    def _body(generate, request, label=""):
        result = run_sql_pipeline(generate, request,
                                  execute_sql=execute_sql, schema=schema, max_attempts=max_attempts,
                                  label=label)
        if result["geojson"] is not None:
            ctx["geojson"] = result["geojson"]
        return result["summary"]

    @tool
    def query_intel(request: str) -> str:
        """Search EXISTING intel already in the database: find, locate, list, count or
        analyze metro stations, parks, hospitals and infrastructure in Milan."""
        return _body(generate_query_sql, request, "query_intel")

    @tool
    def draw_geometry(request: str) -> str:
        """Synthesize a NEW geometry on the map (patrol zone, perimeter, area of operations,
        corridor, route, security buffer) from coordinates or a description. Does NOT read the DB."""
        return _body(generate_geometry_sql, request, "draw_geometry")

    return [query_intel, draw_geometry]
