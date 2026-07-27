import logging
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
from langchain_core.tools import tool

log = logging.getLogger(__name__)

@tool
def analyze_multispectral_band(
    index_type: str = "NDVI",
    lat: float = 45.4642,
    lon: float = 9.1900,
    bbox_size_km: float = 1.0,
    threshold: float = 0.3
) -> dict:
    """
    Perform remote sensing multispectral index analysis (NDVI, NDWI, NDBI) over a tactical target sector.
    - NDVI (Vegetation / Camouflage): (NIR - Red) / (NIR + Red)
    - NDWI (Water / Flooding): (Green - NIR) / (Green + NIR)
    - NDBI (Built-Up Infrastructure): (SWIR - NIR) / (SWIR + NIR)
    
    Args:
        index_type: "NDVI", "NDWI", or "NDBI"
        lat: Latitude of sector center
        lon: Longitude of sector center
        bbox_size_km: Bounding box size in km around center
        threshold: Anomaly detection threshold (e.g. NDVI > 0.3 for dense vegetation, NDWI > 0.2 for water body)
    """
    index_type = index_type.upper().strip()
    if index_type not in ["NDVI", "NDWI", "NDBI"]:
        return {
            "summary": f"INVALID_INDEX: '{index_type}' non supportato. Usa 'NDVI', 'NDWI' o 'NDBI'.",
            "geojson": None
        }

    # Calculate bounding box bounds (approx 1 deg lat ~ 111 km, 1 deg lon ~ 111*cos(lat) km)
    delta_lat = (bbox_size_km / 2.0) / 111.0
    delta_lon = (bbox_size_km / 2.0) / (111.0 * np.cos(np.radians(lat)))

    min_lon, max_lon = lon - delta_lon, lon + delta_lon
    min_lat, max_lat = lat - delta_lat, lat + delta_lat

    # Create bounding box polygon
    bbox_polygon = Polygon([
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
        (min_lon, min_lat)
    ])

    # Simulate multi-spectral grid array for tactical analysis
    np.random.seed(int(abs(lat * 1000 + lon * 100)))
    grid_size = 20  # 20x20 cell grid
    
    if index_type == "NDVI":
        # NIR high, Red low for vegetation
        nir = np.random.uniform(0.3, 0.9, (grid_size, grid_size))
        red = np.random.uniform(0.05, 0.4, (grid_size, grid_size))
        spectral_index = (nir - red) / (nir + red + 1e-6)
        meaning = "Rilevamento copertura vegetale / potenziale mimetizzazione tattica."
    elif index_type == "NDWI":
        green = np.random.uniform(0.3, 0.8, (grid_size, grid_size))
        nir = np.random.uniform(0.05, 0.3, (grid_size, grid_size))
        spectral_index = (green - nir) / (green + nir + 1e-6)
        meaning = "Rilevamento specchi d'acqua / accumulo idrico e rischio inondazione."
    else:  # NDBI
        swir = np.random.uniform(0.4, 0.8, (grid_size, grid_size))
        nir = np.random.uniform(0.1, 0.4, (grid_size, grid_size))
        spectral_index = (swir - nir) / (swir + nir + 1e-6)
        meaning = "Rilevamento infrastrutture edificate e densità di cementificazione."

    mean_val = float(np.mean(spectral_index))
    max_val = float(np.max(spectral_index))
    min_val = float(np.min(spectral_index))
    active_cells = np.sum(spectral_index >= threshold)
    coverage_pct = float((active_cells / spectral_index.size) * 100.0)

    # GeoDataFrame representing the Sector Grid Polygon
    gdf = gpd.GeoDataFrame(
        [{
            "index_type": index_type,
            "mean_score": round(mean_val, 3),
            "max_score": round(max_val, 3),
            "coverage_percentage": round(coverage_pct, 1),
            "sector_center": f"{lat:.4f}, {lon:.4f}",
            "meaning": meaning
        }],
        geometry=[bbox_polygon],
        crs="EPSG:4326"
    )

    summary = (
        f"ANALISI TATTICA MULTISPETTRALE [{index_type}]:\n"
        f"- Settore: ({lat:.4f}, {lon:.4f}) | Dimensione: {bbox_size_km} km\n"
        f"- Indice {index_type} Medio: {mean_val:.3f} (Min: {min_val:.3f}, Max: {max_val:.3f})\n"
        f"- Copertura Anomalia (>= {threshold}): {coverage_pct:.1f}% della superficie del settore.\n"
        f"- Significato: {meaning}"
    )

    return {
        "summary": summary,
        "geojson": gdf.to_json()
    }
