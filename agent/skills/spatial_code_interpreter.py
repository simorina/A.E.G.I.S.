import io
import sys
import logging
import traceback
from typing import Dict, Any
from langchain_core.tools import tool
import geopandas as gpd
import pandas as pd
import numpy as np
import shapely
from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiPolygon, shape
from shapely.ops import voronoi_diagram, unary_union

log = logging.getLogger(__name__)

# Allowed safe modules in sandbox
# Custom safe import function to allow only approved spatial libraries
ALLOWED_MODULES = {"geopandas", "pandas", "numpy", "shapely", "scipy", "sklearn", "math", "json"}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root_module = name.split(".")[0]
    if root_module in ALLOWED_MODULES:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Import of module '{name}' is not allowed in sandbox.")

SAFE_GLOBALS = {
    "__builtins__": {
        "__import__": safe_import,
        "range": range, "len": len, "int": int, "float": float, "str": str,
        "list": list, "dict": dict, "set": set, "tuple": tuple, "bool": bool,
        "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
        "sorted": sorted, "enumerate": enumerate, "zip": zip, "print": print,
        "isinstance": isinstance, "any": any, "all": all, "True": True, "False": False, "None": None
    },
    "gpd": gpd,
    "pd": pd,
    "np": np,
    "shapely": shapely,
    "Point": Point,
    "LineString": LineString,
    "Polygon": Polygon,
    "MultiPoint": MultiPoint,
    "MultiPolygon": MultiPolygon,
    "shape": shape,
    "voronoi_diagram": voronoi_diagram,
    "unary_union": unary_union,
}

@tool
def spatial_code_interpreter(python_code: str) -> dict:
    """
    Execute sandboxed Python code with GeoPandas and Shapely for advanced spatial analytics 
    (e.g., Voronoi diagrams, convex hull perimeters, spatial clustering, custom buffer transformations).
    Assign your final output GeoDataFrame or GeoJSON string to variable `result_geojson` or `result_gdf`.
    
    Example input python_code:
      points = [Point(9.19, 45.46), Point(9.20, 45.47), Point(9.18, 45.45)]
      mp = MultiPoint(points)
      vor = voronoi_diagram(mp)
      result_gdf = gpd.GeoDataFrame(geometry=[g for g in vor.geoms], crs="EPSG:4326")
    """
    # Block dangerous keywords
    forbidden = ["import os", "import sys", "subprocess", "open(", "eval(", "exec(", "builtins", "__import__"]
    for kw in forbidden:
        if kw in python_code:
            return {
                "summary": f"SECURITY_ERROR: Code contains forbidden keyword '{kw}'. Execution blocked.",
                "geojson": None
            }

    # Redirect stdout
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output

    local_vars: Dict[str, Any] = {}
    try:
        exec(python_code, SAFE_GLOBALS, local_vars)
        sys.stdout = old_stdout
        printed_output = redirected_output.getvalue().strip()

        geojson_out = None
        if "result_geojson" in local_vars:
            res = local_vars["result_geojson"]
            geojson_out = res if isinstance(res, str) else str(res)
        elif "result_gdf" in local_vars:
            gdf = local_vars["result_gdf"]
            if isinstance(gdf, gpd.GeoDataFrame):
                geojson_out = gdf.to_json()
        elif "result_geom" in local_vars:
            geom = local_vars["result_geom"]
            gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
            geojson_out = gdf.to_json()

        summary_parts = []
        if printed_output:
            summary_parts.append(f"Output:\n{printed_output}")
        if geojson_out:
            summary_parts.append("Spatial analysis generated valid GeoJSON layer.")
        else:
            summary_parts.append("Code executed successfully without GeoJSON output.")

        return {
            "summary": "\n".join(summary_parts),
            "geojson": geojson_out
        }

    except Exception as exc:
        sys.stdout = old_stdout
        err_msg = f"EXECUTION_ERROR: {exc}\n{traceback.format_exc(limit=2)}"
        log.warning("spatial_code_interpreter failed: %s", exc)
        return {
            "summary": err_msg,
            "geojson": None
        }
