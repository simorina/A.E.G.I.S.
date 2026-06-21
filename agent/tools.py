import logging

from langchain_core.tools import tool

from .safety import extract_sql, validate_readonly_sql, UnsafeQueryError

log = logging.getLogger(__name__)


def make_tools(*, generate_query_sql, generate_geometry_sql, execute_sql,
               schema, ctx, max_attempts=3):
    """Crea i tool legabili al modello; scrivono il GeoJSON prodotto in ctx['geojson']."""

    def _run_sql_pipeline(generate, request, label):
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
                return f"REQUEST_DENIED: unsafe query blocked ({exc})."
            try:
                gdf = execute_sql(sql)
            except Exception as exc:  # noqa: BLE001 - error fed back to the LLM
                error = str(exc)
                log.warning("%s attempt %d failed: %s", label, attempt + 1, exc)
                continue
            if gdf.empty:
                return "No tactical data found in this sector."
            ctx["geojson"] = gdf.to_json()
            return gdf.drop(columns=["geom", "geometry"], errors="ignore").to_string()
        return f"SYSTEM_FAILURE: {error}"

    @tool
    def query_intel(request: str) -> str:
        """Search EXISTING intel already in the database: find, locate, list, count or
        analyze metro stations, parks, hospitals and infrastructure in Milan."""
        return _run_sql_pipeline(generate_query_sql, request, "query_intel")

    @tool
    def draw_geometry(request: str) -> str:
        """Synthesize a NEW geometry on the map (patrol zone, perimeter, area of
        operations, corridor, route, security buffer) from coordinates or a description.
        Does NOT read the database."""
        return _run_sql_pipeline(generate_geometry_sql, request, "draw_geometry")

    return [query_intel, draw_geometry]
