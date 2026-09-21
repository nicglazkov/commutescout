"""The app's server side: /api/nav/route keeps the Stadia key here,
forces the profile, adds closure exclusions and alternates, and relays
the OSRM answer; the tile proxy serves the base map with a day of edge
cache; the style points at it."""

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import nav
from ca_roads_mcp import server as tools

LOCS = [{"lat": 37.35, "lon": -121.94, "type": "break", "heading": 90},
        {"lat": 37.37, "lon": -122.11, "type": "break"}]
FERROSTAR_BODY = {"format": "osrm", "filters": {"action": "include", "attributes": ["x"]},
                  "banner_instructions": True, "voice_instructions": True, "costing": "bicycle",
                  "locations": LOCS, "units": "miles", "api_key": "leak-me"}


def test_nav_body_owns_the_profile_exclusions_and_alternates(monkeypatch):
    monkeypatch.setattr(nav, "NAV_COSTING", "auto_traffic")
    body = nav.nav_body(FERROSTAR_BODY, nav._locations(LOCS), [{"lat": 1, "lon": 2}])
    assert body["costing"] == "auto_traffic"
    assert body["alternates"] == 2 and body["exclude_locations"] == [{"lat": 1, "lon": 2}]
    assert body["format"] == "osrm" and body["banner_instructions"] is True
    assert "api_key" not in body
    assert body["locations"][0]["heading"] == 90
    three = nav.nav_body(FERROSTAR_BODY, nav._locations(LOCS + [LOCS[0]]), [])
    assert "alternates" not in three and "exclude_locations" not in three


class _Resp:
    def __init__(self, status, content=b'{"code":"Ok","routes":[]}'):
        self.status_code = status
        self.content = content
        self.headers = {"content-type": "application/json"}


class _Client:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def post(self, url, *, json, headers, timeout):
        self.calls.append(dict(json))  # a copy: the handler mutates its body on retry
        return self.replies.pop(0)

    async def get(self, url, *, headers, timeout):
        self.calls.append(url)
        return _Resp(200, b"PNG")


def _wire(monkeypatch, client):
    class _Road:
        pass

    road = _Road()
    road.client = client
    monkeypatch.setattr(tools, "get_road", lambda: road)
    monkeypatch.setenv("STADIA_API_KEY", "k")
    demo_app.paid_use = demo_app.DailyCounter()


@pytest.fixture
def wired(monkeypatch):
    client = _Client([_Resp(200)])

    class _Road:
        pass

    road = _Road()
    road.client = client
    monkeypatch.setattr(tools, "get_road", lambda: road)

    async def fake_build(box, want, *, geo_only=False, near=None):
        assert want == {"closure", "plugin"}
        closure = {"kind": "lane_closure", "cls": "full-roadway", "lat": 37.36, "lon": -122.0}
        return [closure], 1, 1, False

    monkeypatch.setattr(demo_app, "build_markers", fake_build)
    monkeypatch.setenv("STADIA_API_KEY", "k")
    nav._TILES.clear()
    return client


def test_nav_route_relays_osrm_with_exclusions(wired):
    c = TestClient(demo_app.app)
    assert c.post("/api/nav/route", json={"locations": [LOCS[0]]}).status_code == 400
    r = c.post("/api/nav/route", json=FERROSTAR_BODY)
    assert r.status_code == 200, r.text
    assert r.json() == {"code": "Ok", "routes": []}
    assert r.headers["x-nav-exclusions"] == "1" and r.headers["x-nav-costing"] == "auto"
    sent = wired.calls[0]
    assert sent["exclude_locations"] == [{"lat": 37.36, "lon": -122.0}]
    assert sent["costing"] == "auto" and "api_key" not in sent


def test_nav_route_retries_without_exclusions_when_stadia_refuses(wired):
    wired.replies = [_Resp(400, b'{"error":"no path"}'), _Resp(200)]
    r = TestClient(demo_app.app).post("/api/nav/route", json=FERROSTAR_BODY)
    assert r.status_code == 200
    assert "exclude_locations" in wired.calls[0] and "exclude_locations" not in wired.calls[1]


def test_nav_route_without_key_is_503(wired, monkeypatch):
    monkeypatch.delenv("STADIA_API_KEY")
    assert TestClient(demo_app.app).post("/api/nav/route", json=FERROSTAR_BODY).status_code == 503


def test_style_can_be_dark_or_outdoors_but_nothing_else(wired):
    c = TestClient(demo_app.app)
    dark = c.get("/api/tiles/style.json?style=alidade_smooth_dark").json()
    assert "/api/tiles/alidade_smooth_dark/" in dark["sources"]["base"]["tiles"][0]
    out = c.get("/api/tiles/style.json?style=outdoors").json()
    assert "/api/tiles/outdoors/" in out["sources"]["base"]["tiles"][0]
    assert c.get("/api/tiles/style.json?style=satellite").status_code == 400
    plain = c.get("/api/tiles/style.json").json()
    assert "/api/tiles/alidade_smooth/" in plain["sources"]["base"]["tiles"][0]


def test_style_points_at_the_proxy_and_tiles_are_cached(wired):
    c = TestClient(demo_app.app)
    style = c.get("/api/tiles/style.json").json()
    base = style["sources"]["base"]
    assert base["tiles"][0].endswith("/api/tiles/alidade_smooth/{z}/{x}/{y}@2x.png")
    assert base["tileSize"] == 256 and "Stadia" in base["attribution"]
    r = c.get("/api/tiles/alidade_smooth/12/655/1583@2x.png")
    assert r.status_code == 200 and r.content == b"PNG"
    assert r.headers["cache-control"].startswith("public, max-age=86400")
    assert wired.calls[-1].endswith("/alidade_smooth/12/655/1583@2x.png")
    n = len(wired.calls)
    assert c.get("/api/tiles/alidade_smooth/12/655/1583@2x.png").status_code == 200
    assert len(wired.calls) == n  # served from memory
    assert c.get("/api/tiles/evil/1/0/0.png").status_code == 404
    assert c.get("/api/tiles/alidade_smooth/1/9/0.png").status_code == 404  # x out of range


def test_budgets_and_limiters_cover_the_new_routes():
    # One caller stays under the service-wide cap for the same upstream.
    assert demo_app.PAID_PER_CLIENT_DAILY["nav"] <= nav.STADIA_NAV_DAILY
    assert demo_app.PAID_PER_CLIENT_DAILY["tiles"] <= nav.STADIA_APP_TILES_DAILY
    assert "/api/nav" in demo_app.SoftLimit.PREFIXES


# A zero-length route: the shape starts at the road point nearest the
# click and the first maneuver names the street (East Santa Clara Street
# at 37.339235, -121.885653).
ROUTE0 = (b'{"trip":{"status":0,"legs":[{"shape":"ee_ffAh|hngF??",'
          b'"maneuvers":[{"type":2,"street_names":["East Santa Clara Street"]},{"type":5}]}]}}')


def test_snap_moves_a_report_onto_a_nearby_road(monkeypatch):
    client = _Client([_Resp(200, ROUTE0)])
    _wire(monkeypatch, client)
    c = TestClient(demo_app.app)
    r = c.get("/api/snap?lat=37.33905&lon=-121.88605").json()
    assert r["snapped"] is True and r["road"] == "East Santa Clara Street"
    assert r["lat"] == 37.339235 and r["lon"] == -121.885653 and 0 < r["distance_m"] < 60
    assert client.calls[0]["locations"] == [
        {"lat": 37.33905, "lon": -121.88605}, {"lat": 37.33905, "lon": -121.88605}]


def test_snap_leaves_a_far_spot_alone(monkeypatch):
    client = _Client([_Resp(200, ROUTE0)])
    _wire(monkeypatch, client)
    c = TestClient(demo_app.app)
    r = c.get("/api/snap?lat=37.3420&lon=-121.8860").json()   # 310 m north of the road
    assert r["snapped"] is False and r["lat"] == 37.342 and r["road"] is None


def test_snap_without_a_key_or_on_error_is_the_click_itself(monkeypatch):
    client = _Client([_Resp(500, b"{}")])
    _wire(monkeypatch, client)
    c = TestClient(demo_app.app)
    assert c.get("/api/snap?lat=37.3&lon=-121.9").json()["snapped"] is False
    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    assert c.get("/api/snap?lat=37.3&lon=-121.9").json() == {
        "snapped": False, "lat": 37.3, "lon": -121.9, "road": None, "distance_m": 0}
    assert c.get("/api/snap?lat=x&lon=1").status_code == 400
