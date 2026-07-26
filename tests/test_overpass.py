import pytest

from agent import overpass as ov
from agent.overpass import (fetch_street, fetch_streets, resolve_place, bbox_from_viewport,
                            _match_names, _street_names_in_bbox)


@pytest.fixture(autouse=True)
def _clean_overpass_state():
    """Ogni test parte con cache vuota e throttle azzerato."""
    ov._cache.clear()
    ov._state["last"] = 0.0
    yield
    ov._cache.clear()


class FakeHttpPost:
    def __init__(self, result=None, raises=None):
        self.result = result
        self.raises = raises
        self.last = None
        self.calls = 0

    def __call__(self, url, data, headers, timeout):
        self.calls += 1
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

def _noop(_):
    pass


def test_fetch_street_merges_ways_into_multilinestring():
    g = fetch_street("Via Monte Napoleone", (45.45, 9.16, 45.49, 9.22),
                     http_post=FakeHttpPost(result=OVERPASS_WAYS), sleep=_noop)
    assert g["type"] == "MultiLineString"
    assert len(g["coordinates"]) == 2
    assert g["coordinates"][0][0] == [9.195, 45.468]  # [lon, lat]


def test_fetch_street_empty_returns_none():
    assert fetch_street("x", (0, 0, 1, 1),
                        http_post=FakeHttpPost(result={"elements": []}), sleep=_noop) is None


def test_fetch_street_exception_returns_none():
    assert fetch_street("x", (0, 0, 1, 1),
                        http_post=FakeHttpPost(raises=RuntimeError("rate")), sleep=_noop) is None


def test_fetch_street_query_is_case_insensitive_and_has_bbox():
    http = FakeHttpPost(result=OVERPASS_WAYS)
    fetch_street("Via X", (45.4, 9.1, 45.5, 9.2), http_post=http, sleep=_noop)
    q = http.last["data"]["data"]
    assert '"name"~"^Via X$",i' in q
    assert "45.4,9.1,45.5,9.2" in q


# --- cache ---

def test_cache_avoids_second_http_call():
    http = FakeHttpPost(result=OVERPASS_WAYS)
    bbox = (45.4, 9.1, 45.5, 9.2)
    fetch_street("Via X", bbox, http_post=http, sleep=_noop)
    fetch_street("Via X", bbox, http_post=http, sleep=_noop)
    assert http.calls == 1  # la seconda volta arriva dalla cache


def test_failures_are_not_cached():
    calls = {"n": 0}

    def flaky(url, data, headers, timeout):
        calls["n"] += 1
        if calls["n"] <= 3:      # primo fetch: 1 tentativo + 2 retry -> fallisce
            raise RuntimeError("429")
        return OVERPASS_WAYS

    bbox = (45.4, 9.1, 45.5, 9.2)
    assert fetch_street("Via X", bbox, http_post=flaky, sleep=_noop) is None
    g = fetch_street("Via X", bbox, http_post=flaky, sleep=_noop)
    assert g is not None  # il fallimento non era in cache: ritenta e riesce


# --- fuzzy match ---

def test_match_names_handles_case_and_small_differences():
    available = ["Corso Vittorio Emanuele II", "Via Dante", "Corso Buenos Aires"]
    out = _match_names(["corso vittorio emanuele", "VIA DANTE"], available)
    assert out["corso vittorio emanuele"] == "Corso Vittorio Emanuele II"
    assert out["VIA DANTE"] == "Via Dante"


def test_match_names_drops_unrelated():
    assert _match_names(["Piazza Inesistente"], ["Via Dante"]) == {}


def test_street_names_in_bbox_parses_tags():
    data = {"elements": [
        {"type": "way", "tags": {"name": "Via A"}},
        {"type": "way", "tags": {"name": "Via B"}},
        {"type": "way", "tags": {}},
    ]}
    names = _street_names_in_bbox((0, 0, 1, 1), FakeHttpPost(result=data), _noop)
    assert names == ["Via A", "Via B"]


def test_fetch_streets_fuzzy_matches_real_name():
    """Il nome richiesto e' leggermente diverso: deve essere abbinato al nome OSM reale."""
    names_resp = {"elements": [{"type": "way", "tags": {"name": "Corso Vittorio Emanuele II"}}]}
    geom_resp = {"elements": [
        {"type": "way", "tags": {"name": "Corso Vittorio Emanuele II"},
         "geometry": [{"lat": 45.46, "lon": 9.19}, {"lat": 45.47, "lon": 9.20}]},
    ]}

    def fake(url, data, headers, timeout):
        return names_resp if "out tags" in data["data"] else geom_resp

    out = fetch_streets(["Corso Vittorio Emanuele"], (45.4, 9.1, 45.5, 9.2),
                        http_post=fake, sleep=_noop)
    assert list(out) == ["Corso Vittorio Emanuele II"]  # chiavato sul nome OSM reale
    assert out["Corso Vittorio Emanuele II"]["type"] == "MultiLineString"


def test_fetch_street_retries_on_error_then_succeeds():
    calls = {"n": 0}

    def flaky(url, data, headers, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("429 rate limited")
        return OVERPASS_WAYS

    g = fetch_street("Via X", (0, 0, 1, 1), http_post=flaky, sleep=_noop)
    assert g["type"] == "MultiLineString"
    assert calls["n"] == 2  # ha ritentato dopo il primo errore


def test_fetch_street_gives_up_after_retries():
    calls = {"n": 0}

    def always_fail(url, data, headers, timeout):
        calls["n"] += 1
        raise RuntimeError("429")

    assert fetch_street("Via X", (0, 0, 1, 1), http_post=always_fail, sleep=_noop) is None
    assert calls["n"] == 3  # 1 tentativo + 2 retry


# --- fetch_streets (batch) ---

OVERPASS_NAMED = {"elements": [
    {"type": "way", "tags": {"name": "Via A"}, "geometry": [{"lat": 1, "lon": 2}, {"lat": 3, "lon": 4}]},
    {"type": "way", "tags": {"name": "Via A"}, "geometry": [{"lat": 3, "lon": 4}, {"lat": 5, "lon": 6}]},
    {"type": "way", "tags": {"name": "Via B"}, "geometry": [{"lat": 7, "lon": 8}, {"lat": 9, "lon": 10}]},
]}


def _batch_http(names_resp, geom_resp):
    """Fake HTTP che distingue la query dei nomi (out tags) da quella delle geometrie (out geom)."""
    calls = {"queries": []}

    def post(url, data, headers, timeout):
        q = data["data"]
        calls["queries"].append(q)
        return names_resp if "out tags" in q else geom_resp

    post.calls = calls
    return post


def test_fetch_streets_groups_by_name_in_single_geometry_query():
    names_resp = {"elements": [{"type": "way", "tags": {"name": "Via A"}},
                               {"type": "way", "tags": {"name": "Via B"}}]}
    http = _batch_http(names_resp, OVERPASS_NAMED)
    out = fetch_streets(["Via A", "Via B"], (45.4, 9.1, 45.5, 9.2), http_post=http, sleep=_noop)
    assert set(out) == {"Via A", "Via B"}
    assert out["Via A"]["type"] == "MultiLineString"
    assert len(out["Via A"]["coordinates"]) == 2  # due tratti di Via A
    assert len(out["Via B"]["coordinates"]) == 1
    geom_q = [q for q in http.calls["queries"] if "out geom" in q][-1]
    assert 'name"="Via A"' in geom_q and 'name"="Via B"' in geom_q  # UNA query per le geometrie


def test_fetch_streets_empty_returns_empty_dict():
    out = fetch_streets(["X"], (0, 0, 1, 1),
                        http_post=FakeHttpPost(result={"elements": []}), sleep=_noop)
    assert out == {}


def test_bbox_from_viewport():
    vp = {"lat": 45.46, "lon": 9.19, "north": 45.5, "south": 45.4, "east": 9.3, "west": 9.1}
    assert bbox_from_viewport(vp) == (45.4, 9.1, 45.5, 9.3)  # (s,w,n,e)
    assert bbox_from_viewport(None) is None


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
