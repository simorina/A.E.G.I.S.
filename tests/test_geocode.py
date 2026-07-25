from agent.geocode import geocode, viewbox_from_viewport, current_viewport


class FakeHttp:
    """Fake HTTP get: ritorna un JSON prefissato e registra l'ultima chiamata."""
    def __init__(self, result=None, raises=None):
        self.result = result
        self.raises = raises
        self.last = None

    def __call__(self, url, params, headers, timeout):
        self.last = {"url": url, "params": params, "headers": headers, "timeout": timeout}
        if self.raises:
            raise self.raises
        return self.result


NOMINATIM_LINE = [{
    "display_name": "Via Monte Napoleone, Milano",
    "lat": "45.4677", "lon": "9.1957",
    "geojson": {"type": "LineString", "coordinates": [[9.195, 45.468], [9.197, 45.466]]},
}]


def test_geocode_returns_real_geometry():
    out = geocode("Via Monte Napoleone", http_get=FakeHttp(result=NOMINATIM_LINE))
    assert out["lat"] == 45.4677 and out["lon"] == 9.1957
    assert out["name"].startswith("Via Monte Napoleone")
    assert out["geometry"]["type"] == "LineString"


def test_geocode_no_result_returns_none():
    assert geocode("nowhere", http_get=FakeHttp(result=[])) is None


def test_geocode_exception_returns_none():
    assert geocode("x", http_get=FakeHttp(raises=RuntimeError("timeout"))) is None


def test_geocode_point_fallback_when_no_geojson():
    res = [{"display_name": "POI", "lat": "45.0", "lon": "9.0"}]
    out = geocode("poi", http_get=FakeHttp(result=res))
    assert out["geometry"] == {"type": "Point", "coordinates": [9.0, 45.0]}


def test_geocode_passes_viewbox_and_bounded():
    http = FakeHttp(result=NOMINATIM_LINE)
    geocode("x", viewbox=(9.1, 45.5, 9.3, 45.4), http_get=http)
    assert http.last["params"]["viewbox"] == "9.1,45.5,9.3,45.4"
    assert http.last["params"]["bounded"] == 0
    assert http.last["params"]["polygon_geojson"] == 1


def test_viewbox_from_viewport():
    vp = {"lat": 45.46, "lon": 9.19, "north": 45.5, "south": 45.4, "east": 9.3, "west": 9.1}
    assert viewbox_from_viewport(vp) == (9.1, 45.5, 9.3, 45.4)
    assert viewbox_from_viewport(None) is None


def test_current_viewport_default_is_none():
    assert current_viewport.get() is None
