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


def test_incident_detail_roundtrip(monkeypatch):
    monkeypatch.setattr(demo_app.tools, "get_road", lambda: FakeRoad())
    client = TestClient(demo_app.app)
    res = client.get("/api/incident/260718GG0075")
    assert res.status_code == 200
    d = res.json()
    assert d["location_desc"] == "EB AT THE ONRAMP"
    assert d["details"][1][1] == "[18] X2 TOYT COA / HOND SUV"
    assert d["units"] == [["Jul 18 2026 12:40AM", "Unit Enroute"]]


def test_incident_not_found_and_bad_id(monkeypatch):
    monkeypatch.setattr(demo_app.tools, "get_road", lambda: FakeRoad())
    client = TestClient(demo_app.app)
    assert client.get("/api/incident/999999ZZ9999").status_code == 404
    assert client.get("/api/incident/x").status_code == 400
    assert client.get("/api/incident/bad.id.here").status_code == 400
    # isalnum() alone would accept non-ASCII letters; the check is ASCII-strict.
    assert client.get("/api/incident/%D0%B0%D0%B1%D0%B2%D0%B3%D0%B4%D0%B5").status_code == 400
