import logging
import urllib.request
import json
import geopandas as gpd
from shapely.geometry import Point
from langchain_core.tools import tool
from agent.geometry import buffer_geometry

log = logging.getLogger(__name__)

@tool
def get_tactical_weather(lat: float = 45.4642, lon: float = 9.1900) -> dict:
    """
    Get live tactical weather conditions (temperature, wind speed, wind direction, cloud cover, visibility, humidity) 
    for target coordinates via Open-Meteo API.
    Essential for drone flight operations, smoke/gas dispersion modeling, and operational planning.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m,cloud_cover"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AEGIS-Tactical-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            current = data.get("current", {})
            temp = current.get("temperature_2m")
            humidity = current.get("relative_humidity_2m")
            wind_spd = current.get("wind_speed_10m")
            wind_dir = current.get("wind_direction_10m")
            clouds = current.get("cloud_cover")

            # Wind vector cardinal direction
            cardinals = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            cardinal = cardinals[int((wind_dir + 11.25) / 22.5) % 16] if wind_dir is not None else "N/A"

            summary = (
                f"CONDIZIONI METEO TATTICHE [{lat:.4f}, {lon:.4f}]:\n"
                f"- Temperatura: {temp} °C | Umidità: {humidity}%\n"
                f"- Vento: {wind_spd} km/h (Provenienza: {wind_dir}° {cardinal})\n"
                f"- Copertura Nuvolosa: {clouds}%\n"
                f"- Valutazione Operativa Droni: {'OTTIMALE' if wind_spd < 25 and clouds < 80 else 'ATTENZIONE VENTO/NUBI'}"
            )
            
            # Point GeoJSON
            p = Point(lon, lat)
            gdf = gpd.GeoDataFrame(
                [{
                    "name": "Target Weather Station",
                    "lat": lat, "lon": lon,
                    "temp_c": temp,
                    "wind_kmh": wind_spd,
                    "wind_dir_cardinal": cardinal
                }],
                geometry=[p],
                crs="EPSG:4326"
            )
            return {"summary": summary, "geojson": gdf.to_json()}

    except Exception as exc:
        log.warning("get_tactical_weather API call failed: %s", exc)
        return {
            "summary": f"WEATHER_OFFLINE: Impossibile recuperare dati meteo in tempo reale ({exc}).",
            "geojson": None
        }

@tool
def calculate_elevation_profile(lat: float = 45.4642, lon: float = 9.1900, observer_height_m: float = 2.0) -> dict:
    """
    Query ground elevation (meters above sea level) and compute an estimated 
    tactical Line-Of-Sight (LOS / Viewshed) radius around observer coordinates.
    """
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AEGIS-Tactical-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            elevations = data.get("elevation", [0])
            elevation_m = elevations[0] if elevations else 0

            total_obs_height = elevation_m + observer_height_m
            # Simple horizon distance formula: d_km ~ 3.57 * sqrt(h_m)
            los_radius_km = round(3.57 * (total_obs_height ** 0.5), 2)
            los_radius_m = int(los_radius_km * 1000)

            # Create buffer geometry around point representing viewshed boundary
            point_geom = {"type": "Point", "coordinates": [lon, lat]}
            buf_geojson = buffer_geometry(point_geom, los_radius_m)

            summary = (
                f"ANALISI ELEVAZIONE E CAMPO VISIVO (VIEWSHED):\n"
                f"- Coordinate Osservatore: ({lat:.4f}, {lon:.4f})\n"
                f"- Quota Terreno: {elevation_m} m s.l.m. (Altezza Osservatore: +{observer_height_m}m = {total_obs_height}m)\n"
                f"- Orizzonte Visivo Teorico (LOS): ~{los_radius_km} km ({los_radius_m}m radius)\n"
                f"- Geometria campo visivo renderizzata su Leaflet."
            )
            return {"summary": summary, "geojson": buf_geojson}

    except Exception as exc:
        log.warning("calculate_elevation_profile failed: %s", exc)
        return {
            "summary": f"ELEVATION_OFFLINE: Impossibile recuperare dati quota DEM ({exc}).",
            "geojson": None
        }
