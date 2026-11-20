"""State feeds that were fetched "successfully" but never reached the map.

Production, 2026-11-20: /api/sources listed 511NY, MiDrive, MDOT
Traffic (MS), FDOT DIVAS and VDOT as "live" while /api/mapdata and the
MCP tools had not one record from any of them, and Alabama answered
every event question with nothing. Each fetcher here is driven through
a mock upstream shaped like the real one (2026-11-20), and the result is
pushed through markers_for_bbox, the exact path /api/mapdata and the
snapshot publisher use, for a box in that state.
"""

import json
import time

import httpx
import pytest

from ca_roads.cache import TTLCache
from ca_roads_demo import app as demo_app
from ca_roads_demo import freshness, states

NOW = time.time()


def _iso(offset_s: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW + offset_s))


@pytest.fixture
def only(monkeypatch):
    """Make one keyless state the whole registry, on a fresh cache."""
    monkeypatch.setattr(states, "_cache", TTLCache())
    monkeypatch.setattr(states, "_LAST_CAMERAS", {})
    monkeypatch.setattr(states, "_PREWARM_DONE", False)
    for name in ("NEC_STATES", "WZDX_FEEDS", "KEYED_STATES", "TOLL_SOURCES"):
        monkeypatch.setattr(states, name, {})

    def use(code: str):
        monkeypatch.setattr(states, "KEYLESS_STATES",
                            {code: states.KEYLESS_STATES[code]})
    return use


async def _through_mapdata(handler, box, want=("incident", "closure")):
    async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)) as client:
        return await states.markers_for_bbox(client, box, set(want),
                                             budget_seconds=10.0)


# ── Michigan: MiDrive moved to Spring 6 (no trailing-slash matching) ──

MI_INC = [{"latitude": 42.33, "longitude": -83.05, "id": 1182684,
           "title": "Crash on WB I-94",
           "message": "<div><strong>Location: </strong>WB I-94 at Mound"
                      "</div><div><strong>Lanes Blocked: </strong>Right"
                      "</div>"}]
MI_CON = [{"latitude": 42.40, "longitude": -83.10, "id": 9,
           "title": "I-75: Total Closure", "active": True,
           "coordinatePoints": [[-83.10, 42.40], [-83.11, 42.41]]}]
MI_CAM = [{"latitude": 42.49, "longitude": -83.04, "id": 1129,
           "title": "11 Mile @ Mound NB"}]
MI_ROWS = [{"image": '<img id="1129Img" src="https://micamerasimages.net/'
                    'thumbs/c.jpg?item=1">'}]


def _midrive(req: httpx.Request) -> httpx.Response:
    path = req.url.path
    if path.endswith("/"):
        # What Spring 6 answers for the old URLs.
        return httpx.Response(404, text="<html>Not Found</html>")
    return {"/MiDrive/incidents/AllForMap": httpx.Response(200, json=MI_INC),
            "/MiDrive/construction/AllForMap": httpx.Response(200, json=MI_CON),
            "/MiDrive/camera/AllForMap": httpx.Response(200, json=MI_CAM),
            "/MiDrive/camera/list": httpx.Response(200, json=MI_ROWS),
            }.get(path, httpx.Response(404))


async def test_michigan_reaches_the_map_in_detroit(only):
    only("mi")
    out = await _through_mapdata(_midrive, (42.2, -83.4, 42.5, -82.9),
                                 ("incident", "closure", "camera"))
    by_kind = {m["kind"]: m for m in out}
    assert set(by_kind) == {"incident", "lane_closure", "camera"}
    assert all(m["src"] == "MDOT MiDrive" for m in out)
    inc = by_kind["incident"]
    assert (inc["lat"], inc["lon"]) == (42.33, -83.05)
    assert "Mound" in inc["label"] and "<" not in inc["label"]
    clo = by_kind["lane_closure"]
    assert clo["cls"] == "full-roadway"
    assert clo["path"][0] == [42.40, -83.10]      # lat, lon order
    assert by_kind["camera"]["image"].startswith("https://micamerasimages")


async def test_michigan_404_is_an_error_not_an_empty_state():
    def all_404(req):
        return httpx.Response(404, text="<html>Not Found</html>")
    async with httpx.AsyncClient(transport=httpx.MockTransport(all_404)) as c:
        with pytest.raises(httpx.HTTPStatusError):
            await states._fetch_mi(c)


# ── Alabama: ALGO Traffic events and signs, not only cameras ─────────

def _al_loc(lat, lon, route="I-59", cross="Roebuck Pkwy"):
    return {"latitude": lat, "longitude": lon, "city": "Birmingham",
            "displayRouteDesignator": route, "displayCrossStreet": cross,
            "direction": "North"}


AL_EVENTS = [
    {"id": 1, "type": "Incident", "severity": "MinorDelay", "active": True,
     "start": _iso(-3600), "end": _iso(3600), "title": "Abandoned Vehicle",
     "subTitle": "I-59 NB @ MP 135.7", "description": "",
     "startLocation": _al_loc(33.55, -86.75),
     "endLocation": _al_loc(33.55, -86.75)},
    {"id": 2, "type": "Crash", "severity": "MajorDelay", "active": True,
     "start": _iso(-600), "end": None, "title": "Crash",
     "subTitle": "I-65 SB @ MP 255", "description": "Two lanes blocked.",
     "startLocation": _al_loc(33.45, -86.82, "I-65"),
     "endLocation": None},
    {"id": 3, "type": "Roadwork", "severity": "Closed", "active": True,
     "start": _iso(-86400), "end": _iso(86400),
     "title": "Planned Bridge Work", "subTitle": "US-31 at Lakeshore",
     "description": "Road closed.",
     "startLocation": _al_loc(33.46, -86.79, "US-31"),
     "endLocation": _al_loc(33.47, -86.78, "US-31")},
    # Not on the road, and not started yet: both stay off the map.
    {"id": 4, "type": "Facility", "severity": "Closed", "active": True,
     "start": _iso(-60), "end": None, "title": "Rest Area",
     "startLocation": _al_loc(33.5, -86.7)},
    {"id": 5, "type": "Roadwork", "severity": "ModerateDelay",
     "active": True, "start": _iso(86400), "end": _iso(172800),
     "title": "Future work", "startLocation": _al_loc(33.5, -86.7)},
]
AL_CAMS = [{"location": _al_loc(33.52, -86.80),
            "snapshotImageUrl": "https://api.algotraffic.com/cam.jpg",
            "permLink": "https://algotraffic.com/cam"}]
AL_SIGNS = [{"location": _al_loc(33.51, -86.81),
             "pages": [{"lines": [{"text": "CRASH AHEAD"},
                                  {"text": "USE CAUTION"}]}]}]


def _algo(req: httpx.Request) -> httpx.Response:
    return {"/v4.0/TrafficEvents": httpx.Response(200, json=AL_EVENTS),
            "/v4.0/cameras": httpx.Response(200, json=AL_CAMS),
            "/v4.0/MessageSigns": httpx.Response(200, json=AL_SIGNS),
            }.get(req.url.path, httpx.Response(404))


async def test_alabama_events_reach_the_map_in_birmingham(only):
    only("al")
    out = await _through_mapdata(_algo, (33.3, -87.0, 33.7, -86.6),
                                 ("incident", "closure", "camera", "sign"))
    assert all(m["src"] == "ALGO Traffic (ALDOT)" for m in out)
    kinds = sorted(m["kind"] for m in out)
    assert kinds == ["camera", "incident", "incident", "lane_closure", "sign"]
    crash = next(m for m in out if m.get("type") == "Crash")
    assert (crash["lat"], crash["lon"]) == (33.45, -86.82)
    assert crash["detail"] == "Two lanes blocked."
    work = next(m for m in out if m["kind"] == "lane_closure")
    assert work["cls"] == "full-roadway"
    assert work["path"] == [[33.46, -86.79], [33.47, -86.78]]
    sign = next(m for m in out if m["kind"] == "sign")
    assert sign["lines"] == ["CRASH AHEAD", "USE CAUTION"]


# ── New York: 511NY's public map layers replace the dead WZDx URL ────

def _ny_feat(eid, geom, active=True, tooltip="I-87 northbound: Crash.",
             headline="", description=""):
    return {"type": "Feature", "geometry": geom, "properties": {
        "id": eid, "active": active, "tooltip": tooltip, "route": "I-87",
        "description": description,
        "eventReport": {"eventDescription": {"headlinePhrase": headline}}}}


NY_LAYERS = {
    "incidents": [
        _ny_feat("TRANSCOM-1", {"type": "Point",
                                "coordinates": [-73.80, 42.70]},
                 headline="Crash", description="<div> Crash at Exit 7 </div>"),
        _ny_feat("TRANSCOM-2", {"type": "Point",
                                "coordinates": [-73.81, 42.71]},
                 active=False),
    ],
    "closures": [
        _ny_feat("TRANSCOM-3", {"type": "LineString", "coordinates": [
            [-73.75, 42.65], [-73.76, 42.66], [-73.77, 42.67]]},
            tooltip="I-90 eastbound: Road closed, because of roadwork.",
            headline="Road Closed"),
    ],
    "construction": [
        # Also listed under closures: drawn once.
        _ny_feat("TRANSCOM-3", {"type": "Point",
                                "coordinates": [-73.75, 42.65]},
                 tooltip="I-90 eastbound: Road closed."),
        _ny_feat("TRANSCOM-4", {"type": "MultiLineString", "coordinates": [
            [[-73.90, 42.80], [-73.91, 42.81]]]},
            tooltip="NY 7 westbound: Right lane closed."),
    ],
}


def _ny(req: httpx.Request) -> httpx.Response:
    if req.url.host == "511ny.org":
        # The old WZDx URL now serves the new site's HTML shell.
        return httpx.Response(200, text="<!doctype html><html></html>")
    layer = req.url.params.get("eventClassifications")
    if req.url.path != "/events/map-features" or layer not in NY_LAYERS:
        return httpx.Response(404)
    return httpx.Response(200, content=json.dumps(
        {"features": NY_LAYERS[layer]}).encode())


async def test_new_york_reaches_the_map_in_albany(only):
    assert "ny" not in states.WZDX_FEEDS
    only("ny")
    out = await _through_mapdata(_ny, (42.5, -74.0, 42.9, -73.6))
    assert all(m["src"] == "511NY" for m in out)
    assert sorted(m["kind"] for m in out) == [
        "incident", "lane_closure", "lane_closure"]
    inc = next(m for m in out if m["kind"] == "incident")
    assert (inc["lat"], inc["lon"]) == (42.70, -73.80)
    assert inc["type"] == "Crash" and inc["detail"] == "Crash at Exit 7"
    closed = next(m for m in out if m["label"].startswith("I-90"))
    assert closed["cls"] == "full-roadway"
    assert closed["path"][0] == [42.65, -73.75] and closed["end"] == [42.67, -73.77]
    lane = next(m for m in out if m["label"].startswith("NY 7"))
    assert lane["cls"] == "lane" and lane["path"][-1] == [42.81, -73.91]


async def test_new_york_rejects_an_html_shell():
    def shell(req):
        return httpx.Response(200, text="<!doctype html><html></html>")
    async with httpx.AsyncClient(transport=httpx.MockTransport(shell)) as c:
        with pytest.raises(ValueError):
            await states._fetch_ny(c)


# ── Florida: DIVAS events moved to a MapServer with PascalCase fields ─

async def test_florida_events_read_the_mapserver_layer(only):
    ev = {"features": [
        {"geometry": {"x": -80.20, "y": 26.10},
         "attributes": {"Status": "confirmed", "EventTypeSae": "Crash",
                        "DescriptionEn": "Crash on I-95 North",
                        "Highway": "I-95", "AffectedLanes": ""}},
        {"geometry": {"x": -80.15, "y": 26.71},
         "attributes": {"Status": "confirmed",
                        "EventTypeSae": "Planned construction",
                        "DescriptionEn": "Left lane blocked",
                        "AffectedLanes": " Left lane blocked",
                        "Highway": "Okeechobee Blvd"}},
    ]}

    def divas(req):
        path = req.url.path
        if "DIVAS_GetEvent/MapServer" in path:
            return httpx.Response(200, json=ev)
        if "DIVAS_GetEvent/FeatureServer" in path:
            return httpx.Response(200, json={"error": {
                "code": 500, "message": "Server object extension "
                "'featureserver' not found."}})
        return httpx.Response(200, json={"features": []})

    only("fl")
    out = await _through_mapdata(divas, (25.5, -80.5, 27.0, -80.0))
    assert all(m["src"] == "FDOT" for m in out)
    crash = next(m for m in out if m["kind"] == "incident")
    assert (crash["lat"], crash["lon"]) == (26.10, -80.20)
    assert crash["label"] == "Crash on I-95 North"
    work = next(m for m in out if m["kind"] == "lane_closure")
    assert work["route"] == "Okeechobee Blvd"


# ── Honest status: a feed that cannot deliver is not "live" ──────────

async def test_a_feed_that_never_answers_is_down_not_live(only, monkeypatch):
    def waf(req):
        return httpx.Response(403, text="Azure WAF")

    only("fl")
    out = await _through_mapdata(waf, (25.5, -80.5, 27.0, -80.0))
    assert out == []
    row = next(r for r in states.source_status() if r["agency"] == "FDOT DIVAS")
    assert row["ok"] is False and row["count"] == 0
    assert "403" in row["error"] and "where=" not in row["error"]
    from datetime import UTC, datetime
    assert demo_app.source_health(dict(row), datetime.now(UTC))["status"] == "down"
    # Not claimed as a covered state or a live source.
    assert states.coverage_summary() == {"sources": 7, "states": 2}
    # Settled for warm-up (an outage, not a wait) ...
    assert states.warm_progress() == (1, 1)
    # ... and alerted on, though it never had an entry to age.
    stale = await _find_state_stale(monkeypatch)
    assert "state feed fl:all" in stale
    assert "no data since start" in stale["state feed fl:all"]


async def _find_state_stale(monkeypatch):
    from ca_roads_mcp import server as tools

    class Quiet:
        async def _ok(self):
            from datetime import UTC, datetime
            from types import SimpleNamespace
            return SimpleNamespace(data_as_of=datetime.now(UTC), error=None)

        def __getattr__(self, name):
            return self._ok

    monkeypatch.setattr(tools, "get_road", lambda: Quiet())
    return await freshness.find_stale()


async def test_a_working_feed_stays_fresh_and_counted(only):
    only("ny")
    await _through_mapdata(_ny, (42.5, -74.0, 42.9, -73.6))
    row = next(r for r in states.source_status() if r["agency"] == "511NY")
    assert row["ok"] is True and row["count"] == 3 and "error" not in row
    assert states.coverage_summary()["states"] == 3   # CA, NV, New York


def test_warm_progress_can_be_scoped_to_a_box(only):
    only("ny")
    albany, reno = (42.5, -74.0, 42.9, -73.6), (39.4, -120.0, 39.6, -119.7)
    assert states.warm_progress(albany) == (0, 1)
    # A box no registered feed touches has nothing to wait for. The MCP
    # fallback build used to count the whole country and so reported
    # "some state feeds were still loading" on every trip.
    assert states.warm_progress(reno) == (0, 0)


async def test_mcp_fallback_does_not_claim_feeds_are_loading(only, monkeypatch):
    """plan_trip's fallback build (no fresh snapshot) only fetches the
    states its box touches; feeds elsewhere being cold is not a reason
    to tell the user events may be missing."""
    from ca_roads_mcp import planning, snapshots

    only("ny")

    async def no_snapshot(*_a, **_k):
        return None

    async def build(box, want, feed_budget=None, **_k):
        # The whole country is "1 of 50 warm", as in a process that
        # never prewarms.
        return [], 1, 50, False

    monkeypatch.setattr(snapshots, "markers", no_snapshot)
    monkeypatch.setattr(demo_app, "build_markers", build)
    reno = (39.4, -120.0, 39.6, -119.7)
    _markers, notes = await planning.live_markers(None, reno, {"incident"})
    assert notes == []
    # A box whose own feed has not answered still says so.
    albany = (42.5, -74.0, 42.9, -73.6)
    _markers, notes = await planning.live_markers(None, albany, {"incident"})
    assert notes and "still loading" in notes[0]
