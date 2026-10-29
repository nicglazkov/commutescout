"""/api/event-status and the push data behind it: a tapped watch alert
opens the event as it is now, or says plainly that it ended."""

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import event_status, watch


@pytest.fixture(autouse=True)
def _fresh():
    event_status.reset()
    yield
    event_status.reset()


def ev(eid, kind="incident", lat=37.44, lon=-122.14, title="Collision"):
    return {"id": eid, "kind": kind, "lat": lat, "lon": lon, "title": title,
            "body": "Somewhere", "meta": "", "payload": {"big": "x"}}


def use_markers(monkeypatch, markers):
    async def fake_build(box, want, **_kw):
        return list(markers), 1, 1, False
    monkeypatch.setattr(demo_app, "build_markers", fake_build)


def get(params):
    return TestClient(demo_app.app).get("/api/event-status", params=params)


def test_cycle_tracks_live_and_cleared():
    event_status.note_cycle([ev("chp:A"), ev("chp:B")], now=1000)
    assert event_status.lookup("chp:A")["state"] == "active"
    event_status.note_cycle([ev("chp:B")], now=1300)
    gone = event_status.lookup("chp:A")
    assert gone["state"] == "cleared" and gone["cleared_at"] == 1300
    assert "payload" not in gone["event"]
    # Back again: live, not cleared.
    event_status.note_cycle([ev("chp:A"), ev("chp:B")], now=1600)
    assert event_status.lookup("chp:A")["state"] == "active"
    # Never seen: unknown.
    assert event_status.lookup("chp:Z")["state"] == "unknown"


def test_first_cycle_after_restart_clears_nothing():
    event_status.note_cycle([ev("chp:A")], now=1000)
    assert event_status.lookup("chp:Q")["state"] == "unknown"


def test_chain_level_change_reads_as_changed():
    event_status.note_cycle([ev("chain:7:R-1", kind="chain")], now=1000)
    event_status.note_cycle(
        [ev("chain:7:R-2", kind="chain", title="Chain control R-2 on I-80")], now=1300)
    got = event_status.lookup("chain:7:R-1")
    assert got["state"] == "changed"
    assert got["event"]["id"] == "chain:7:R-2"


def test_cleared_memory_ages_out():
    event_status.note_cycle([ev("chp:A")], now=0)
    event_status.note_cycle([], now=100)
    event_status.note_cycle([], now=100 + event_status.CLEARED_KEEP_SECONDS + 1)
    assert event_status.lookup("chp:A")["state"] == "unknown"


def test_endpoint_active_returns_the_marker(monkeypatch):
    event_status.note_cycle([ev("chp:A1")], now=1000)
    use_markers(monkeypatch, [
        {"kind": "incident", "id": "OTHER", "lat": 37.4401, "lon": -122.1401},
        {"kind": "incident", "id": "A1", "lat": 37.45, "lon": -122.15},
    ])
    r = get({"id": "chp:A1", "kind": "incident", "lat": 37.44, "lon": -122.14})
    assert r.status_code == 200
    d = r.json()
    assert d["state"] == "active"
    # The same CHP id wins over a closer marker.
    assert d["marker"]["id"] == "A1"
    assert r.headers["cache-control"] == "no-store"


def test_endpoint_cleared_offers_nearby_but_not_as_the_event(monkeypatch):
    event_status.note_cycle([ev("lcs:9", kind="closure")], now=1000)
    event_status.note_cycle([], now=1300)
    use_markers(monkeypatch, [{"kind": "lane_closure", "lat": 37.4402, "lon": -122.1402}])
    d = get({"id": "lcs:9", "kind": "lane_closure", "lat": 37.44, "lon": -122.14}).json()
    assert d["state"] == "cleared"
    assert d["cleared_at"].startswith("1970-01-01T00:21:40")
    assert "marker" not in d
    assert d["nearby"]["kind"] == "lane_closure"
    assert d["kind"] == "lane_closure"


def test_endpoint_unknown_id_falls_back_to_the_map(monkeypatch):
    use_markers(monkeypatch, [])
    d = get({"id": "st:abc", "kind": "fire", "lat": 40.0, "lon": -120.0}).json()
    assert d["state"] == "gone"
    use_markers(monkeypatch, [{"kind": "wildfire", "lat": 40.001, "lon": -120.001, "name": "Oak"}])
    d = get({"id": "st:abc", "kind": "fire", "lat": 40.0, "lon": -120.0}).json()
    assert d["state"] == "active" and d["marker"]["name"] == "Oak"
    # Too far to be the same fire.
    use_markers(monkeypatch, [{"kind": "wildfire", "lat": 40.01, "lon": -120.0}])
    far = get({"id": "st:abc", "kind": "fire", "lat": 40.0, "lon": -120.0}).json()
    assert far["state"] == "gone"


def test_endpoint_rejects_bad_input():
    assert get({"kind": "toll", "lat": 1, "lon": 1}).status_code == 400
    assert get({"kind": "incident", "lat": "x", "lon": 1}).status_code == 400
    assert get({"kind": "incident", "lat": 91, "lon": 1}).status_code == 400


def test_fcm_data_carries_the_event(monkeypatch):
    sent = {}

    class Resp:
        status_code = 200
        text = ""

    def fake_post(url, json, headers, timeout):
        sent.update(json["message"])
        return Resp()

    monkeypatch.setattr(watch, "_fcm_access_token", lambda: "t")
    monkeypatch.setattr(watch.httpx, "post", fake_post)
    assert watch._fcm_send("tok", "ios", {
        "title": "Home: Collision", "body": "I-280", "url": "https://x/?focus=1,2&k=incident",
        "event": {"id": "chp:A", "kind": "incident", "lat": 37.5, "lon": -122.1,
                  "title": "Collision", "sent_at": 1700000000, "body": None},
    })
    data = sent["data"]
    assert data["event_id"] == "chp:A"
    assert data["event_lat"] == "37.5"
    assert data["event_sent_at"] == "1700000000"
    assert "event_body" not in data
    assert all(isinstance(v, str) for v in data.values())


def test_explain_line_matches_the_web_map():
    assert (event_status.explain_line("[1] 2 VEH TC BLKG #2 LN")
            == "[1] 2 vehicle collision blocking #2 lane")
    assert event_status.explain_line("SB JSO OFR") == "southbound just south of off-ramp"
    # Official labels stay verbatim; a line with no shorthand gives None.
    assert event_status.explain_line("1179-Trfc Collision-1141 Enrt") is None
    assert event_status.explain_line("Caller says hello") is None
    assert event_status.explain_line("A62-505 1097") == "unit A62-505 unit on scene"


def test_dispatch_log_newest_first_with_unit_stories():
    d = event_status.dispatch_log(
        [("Jul 18 2026 12:37AM", "[1] 2 VEH TC"), ("Jul 18 2026 12:51AM", "[18] X2 TOYT")],
        [("Jul 18 2026 12:59AM", "Unit Cleared"), ("Jul 18 2026 12:45AM", "Unit At Scene"),
         ("Jul 18 2026 12:40AM", "Unit Enroute"), ("Jul 18 2026 12:39AM", "Unit Assigned"),
         ("Jul 18 2026 12:50AM", "Unit Assigned")])
    assert [r["time"] for r in d["log"]] == ["12:51 AM", "12:37 AM"]
    assert d["log"][0]["plain"] == "[18] X2 Toyota"
    assert d["units"][0]["done"] is True
    assert [s["status"] for s in d["units"][0]["steps"]] == [
        "assigned", "en route", "on scene", "cleared to leave"]
    assert d["units"][1]["done"] is False
