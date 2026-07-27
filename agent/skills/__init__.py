"""
A.E.G.I.S. Advanced Agent Skills Package (Section 2)
Includes:
- Spatial Code Interpreter (Python REPL for GeoPandas/Shapely)
- Remote Sensing Analyst (Multispectral Satellite Analytics: NDVI, NDWI, NDBI)
- Tactical Weather & Elevation (Open-Meteo & DEM Line-of-sight)
- Dynamic Skill Registry (Tool Search & Routing)
"""

from .spatial_code_interpreter import spatial_code_interpreter
from .remote_sensing import analyze_multispectral_band
from .tactical_weather_elevation import get_tactical_weather, calculate_elevation_profile
from .dynamic_registry import SkillRegistry

__all__ = [
    "spatial_code_interpreter",
    "analyze_multispectral_band",
    "get_tactical_weather",
    "calculate_elevation_profile",
    "SkillRegistry",
]
