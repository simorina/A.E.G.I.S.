from agent.geocode import geocode, viewbox_from_viewport, current_viewport


class FakeLoc:
    def __init__(self, address, lat, lon):
        self.address = address
        self.latitude = lat
        self.longitude = lon


class FakeGeocoder:
    def __init__(self, result=None, raises=None):
        self.result = result
        self.raises = raises
        self.calls = []

    def geocode(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if self.raises:
            raise self.raises
        return self.result


def test_geocode_success_returns_dict():
    gc = FakeGeocoder(result=FakeLoc("Prato della Valle, Padova", 45.398, 11.877))
    out = geocode("Prato della Valle", geocoder=gc)
    assert out == {"name": "Prato della Valle, Padova", "lat": 45.398, "lon": 11.877}


def test_geocode_no_result_returns_none():
    assert geocode("nowhere", geocoder=FakeGeocoder(result=None)) is None


def test_geocode_exception_returns_none():
    assert geocode("x", geocoder=FakeGeocoder(raises=RuntimeError("timeout"))) is None


def test_geocode_passes_viewbox():
    gc = FakeGeocoder(result=FakeLoc("X", 1.0, 2.0))
    vb = [(45.5, 9.3), (45.4, 9.1)]
    geocode("X", viewbox=vb, geocoder=gc)
    assert gc.calls[0][1].get("viewbox") == vb


def test_viewbox_from_viewport():
    vp = {"lat": 45.46, "lon": 9.19, "north": 45.5, "south": 45.4, "east": 9.3, "west": 9.1}
    assert viewbox_from_viewport(vp) == [(45.5, 9.3), (45.4, 9.1)]
    assert viewbox_from_viewport(None) is None


def test_current_viewport_default_is_none():
    assert current_viewport.get() is None
