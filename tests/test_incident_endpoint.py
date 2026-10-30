"""/api/incident/{id}: the lazy dispatch-log endpoint behind the
"Show dispatch log" popup button."""

from datetime import UTC, datetime

from starlette.testclient import TestClient

from ca_roads.models import ChpIncident, FeedResult
from ca_roads_demo import app as demo_app

INC = ChpIncident(
    id="260718GG0075",
    log_type="1181-Trfc Collision-Minor Inj",
    location="Sr84 E / University Ave Onr",
    area="Redwood City",
    lat=37.482, lon=-122.14,
    reported_at=datetime(2026, 7, 18, 0, 36, tzinfo=UTC),
    location_desc="EB AT THE ONRAMP",
    details=(("Jul 18 2026 12:37AM", "[1] 2 VEH TC"),
             ("Jul 18 2026 12:51AM", "[18] X2 TOYT COA / HOND SUV")),
    units=(("Jul 18 2026 12:40AM", "Unit Enroute"),),
)


class FakeRoad:
    async def incidents(self):
        return FeedResult(source="chp", records=[INC],
                          data_as_of=datetime(2026, 7, 18, 0, 55, tzinfo=UTC))

    async def _empty(self, source):
        return FeedResult(source=source, records=[],
                          data_as_of=datetime(2026, 7, 18, 0, 50, tzinfo=UTC))

    async def lane_closures(self):
        return await self._empty("lcs")

    async def chain_controls(self):
        return await self._empty("chains")

    async def wildfires(self):
        return await self._empty("wfigs")

    async def cameras(self):
        return await self._empty("cctv")

    async def message_signs(self):
        return await self._empty("cms")

    async def road_weather(self):
        return await self._empty("rwis")


def test_incident_detail_roundtrip(monkeypatch):
    monkeypatch.setattr(demo_app.tools, "get_road", lambda: FakeRoad())
    client = TestClient(demo_app.app)
    res = client.get("/api/incident/260718GG0075")
    assert res.status_code == 200
    d = res.json()
    assert d["location_desc"] == "EB AT THE ONRAMP"
    assert d["details"][1][1] == "[18] X2 TOYT COA / HOND SUV"
    assert d["units"] == [["Jul 18 2026 12:40AM", "Unit Enroute"]]


def test_sources_status(monkeypatch):
    monkeypatch.setattr(demo_app.tools, "get_road", lambda: FakeRoad())
    client = TestClient(demo_app.app)
    res = client.get("/api/sources")
    assert res.status_code == 200
    d = res.json()
    names = [s["name"] for s in d["sources"]]
    assert "Incidents" in names and "Cameras" in names
    chp = next(s for s in d["sources"] if s["name"] == "Incidents")
    assert chp["ok"] is True and chp["count"] == 1 and chp["as_of"]
    nws = next(s for s in d["sources"] if s["agency"] == "NWS")
    assert nws.get("on_demand") is True
    assert d["checked_at"]
    # The data-source screen's fields ride on every entry.
    assert nws["status"] == "live" and nws["group"] == "national"
    assert chp["group"] == "state" and chp["state_code"] == "CA"
    assert chp["status"] in ("fresh", "stale")
    assert all(s["status"] in ("fresh", "stale", "down", "live", "off") for s in d["sources"])
    assert set(d["summary"]) == {"fresh", "stale", "down", "live", "off", "states"}
    assert sum(v for k, v in d["summary"].items() if k != "states") == len(d["sources"])


def test_source_health_classes():
    from datetime import UTC, datetime, timedelta
    now = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)
    ago = lambda m: (now - timedelta(minutes=m)).isoformat()  # noqa: E731
    h = demo_app.source_health
    assert h({"state": "Ohio", "ok": True, "as_of": ago(5)}, now)["status"] == "fresh"
    assert h({"state": "Ohio", "ok": True, "as_of": ago(5)}, now)["age_s"] == 300
    assert h({"state": "Ohio", "ok": True, "as_of": ago(120)}, now)["status"] == "stale"
    assert h({"state": "California", "ok": True, "as_of": ago(25),
              "stale_after_s": 1200}, now)["status"] == "stale"
    stale = {"state": "Ohio", "ok": True, "stale": True, "as_of": ago(1)}
    assert h(stale, now)["status"] == "stale"
    assert h({"state": "Ohio", "ok": False, "as_of": ago(1)}, now)["status"] == "down"
    assert h({"state": "Nevada", "enabled": False}, now)["status"] == "off"
    entry = h({"state": "Maine", "on_demand": True}, now)
    assert entry["status"] == "live" and entry["state_code"] == "ME"


def test_incident_not_found_and_bad_id(monkeypatch):
    monkeypatch.setattr(demo_app.tools, "get_road", lambda: FakeRoad())
    client = TestClient(demo_app.app)
    assert client.get("/api/incident/999999ZZ9999").status_code == 404
    assert client.get("/api/incident/x").status_code == 400
    assert client.get("/api/incident/bad.id.here").status_code == 400
    # isalnum() alone would accept non-ASCII letters; the check is ASCII-strict.
    assert client.get("/api/incident/%D0%B0%D0%B1%D0%B2%D0%B3%D0%B4%D0%B5").status_code == 400


def test_daily_toll_schedule_is_not_stale_at_four_hours():
    from datetime import UTC, datetime, timedelta

    from ca_roads_demo import freshness

    src = {"name": "Toll pricing", "ok": True, "stale": False,
           "as_of": (datetime.now(UTC) - timedelta(hours=4)).isoformat(),
           "stale_after_s": freshness.state_limit("toll:cabr")}
    assert demo_app.source_health(src, datetime.now(UTC))["status"] == "fresh"
    src["stale_after_s"] = freshness.state_limit("toll:baytoll")
    assert demo_app.source_health(src, datetime.now(UTC))["status"] == "stale"
