import json

import geopandas as gpd
from shapely.geometry import shape


def feature_collection(geometry: dict, label: str) -> str:
    """Incapsula una geometria GeoJSON in una FeatureCollection (stringa) con `label`."""
    return json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"label": label},
            "geometry": geometry,
        }],
    })


def buffer_geometry(geometry: dict, radius_m: float) -> str:
    """Buffer metrico accurato attorno a una geometria GeoJSON (WGS84).
    Riproietta in UTM per avere metri corretti, poi torna in 4326.
    Ritorna una FeatureCollection (stringa)."""
    series = gpd.GeoSeries([shape(geometry)], crs=4326)
    utm = series.estimate_utm_crs()
    buffered = series.to_crs(utm).buffer(radius_m).to_crs(4326)
    gdf = gpd.GeoDataFrame({"label": ["buffer"]}, geometry=buffered, crs=4326)
    return gdf.to_json()
