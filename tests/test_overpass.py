from agent.overpass import fetch_street, resolve_place


class FakeHttpPost:
    def __init__(self, result=None, raises=None):
        self.result = result
        self.raises = raises
        self.last = None

    def __call__(self, url, data, headers, timeout):
        self.last = {"url": url, "data": data, "headers": headers, "timeout": timeout}
        if self.raises:
            raise self.raises
        return self.result


OVERPASS_WAYS = {"elements": [
    {"type": "way", "geometry": [{"lat": 45.468, "lon": 9.195}, {"lat": 45.466, "lon": 9.197}]},
    {"type": "way", "geometry": [{"lat": 45.466, "lon": 9.197}, {"lat": 45.464, "lon": 9.199}]},
]}

LINE = {"type": "LineString", "coordinates": [[9.195, 45.468], [9.197, 45.466]]}
POLY = {"type": "Polygon", "coordinates": [[[9, 45], [9, 46], [10, 46], [9, 45]]]}
MLS = {"type": "MultiLineString", "coordinates": [
    [[9.195, 45.468], [9.197, 45.466]], [[9.197, 45.466], [9.199, 45.464]]]}


# --- fetch_street ---

def test_fetch_street_merges_ways_into_multilinestring():
    g = fetch_street("Via Monte Napoleone", (45.45, 9.16, 45.49, 9.22),
                     http_post=FakeHttpPost(result=OVERPASS_WAYS))
    assert g["type"] == "MultiLineString"
    assert len(g["coordinates"]) == 2
    assert g["coordinates"][0][0] == [9.195, 45.468]  # [lon, lat]


def test_fetch_street_empty_returns_none():
    assert fetch_street("x", (0, 0, 1, 1), http_post=FakeHttpPost(result={"elements": []})) is None


def test_fetch_street_exception_returns_none():
    assert fetch_street("x", (0, 0, 1, 1), http_post=FakeHttpPost(raises=RuntimeError("rate"))) is None


def test_fetch_street_query_contains_name_and_bbox():
    http = FakeHttpPost(result=OVERPASS_WAYS)
    fetch_street("Via X", (45.4, 9.1, 45.5, 9.2), http_post=http)
    q = http.last["data"]["data"]
    assert 'name"="Via X"' in q
    assert "45.4,9.1,45.5,9.2" in q


# --- resolve_place ---

def test_resolve_upgrades_street_and_converts_bbox():
    seen = {}
    gc = lambda q, viewbox=None: {"name": "Via Monte Napoleone, Milano",
                                  "lat": 45.467, "lon": 9.196, "geometry": LINE}

    def sf(name, bbox):
        seen["name"] = name
        seen["bbox"] = bbox
        return MLS

    out = resolve_place("Via Monte Napoleone", (9.16, 45.49, 9.22, 45.45),
                        geocode_fn=gc, street_fn=sf)
    assert out["geometry"] == MLS
    assert seen["name"] == "Via Monte Napoleone"       # primo componente del display_name
    assert seen["bbox"] == (45.45, 9.16, 45.49, 9.22)  # (s,w,n,e) da viewbox (w,n,e,s)


def test_resolve_keeps_area_geometry_without_overpass():
    calls = []
    gc = lambda q, viewbox=None: {"name": "Prato della Valle", "lat": 45.398,
                                  "lon": 11.877, "geometry": POLY}
    sf = lambda name, bbox: calls.append(name) or MLS
    out = resolve_place("Prato della Valle", None, geocode_fn=gc, street_fn=sf)
    assert out["geometry"] == POLY
    assert calls == []


def test_resolve_falls_back_when_overpass_empty():
    gc = lambda q, viewbox=None: {"name": "Via X", "lat": 45.4, "lon": 9.1, "geometry": LINE}
    out = resolve_place("Via X", None, geocode_fn=gc, street_fn=lambda name, bbox: None)
    assert out["geometry"] == LINE


def test_resolve_none_when_geocode_none():
    out = resolve_place("nowhere", None,
                        geocode_fn=lambda q, viewbox=None: None,
                        street_fn=lambda n, b: MLS)
    assert out is None
