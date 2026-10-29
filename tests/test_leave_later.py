"""Leave later: departure slots, the best pick, and the endpoint."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from starlette.testclient import TestClient

from ca_roads_demo import app as demo_app
from ca_roads_demo import leavelater

NOW = datetime(2026, 10, 29, 15, 22, tzinfo=UTC)


def test_slots_start_now_then_ten_minute_marks():
    got = leavelater.slots(NOW)
    assert got[0] is None
    assert [d.strftime("%H:%M") for d in got[1:]] == [
        "15:30", "15:40", "15:50", "16:00", "16:10", "16:20"]
    # A mark less than five minutes out is skipped.
    near = datetime(2026, 10, 29, 15, 27, tzinfo=UTC)
    assert leavelater.slots(near)[1].strftime("%H:%M") == "15:40"


def rows(*minutes):
    whens = leavelater.slots(NOW)
    return [(w, {"travel_s": m * 60, "delay_s": 0} if m else None)
            for w, m in zip(whens, minutes, strict=False)]


def test_best_departure_and_saving():
    body = leavelater.summarize(NOW, rows(42, 40, 36, 34, 35, 38, 41))
    assert body["best"] == {"depart_at": "2026-10-29T15:50+00:00", "drive_min": 34,
                            "saving_min": 8}
    assert body["reason"] == "Traffic should ease by then"
    assert body["departures"][0]["now"] is True
    assert [d["drive_min"] for d in body["departures"]] == [42, 40, 36, 34, 35, 38, 41]


def test_small_saving_says_leave_now():
    body = leavelater.summarize(NOW, rows(30, 29, 29, 28, 30, 31, 31))
    assert body["best"] is None
    assert body["reason"].startswith("Leaving now")


def test_missing_slots_are_null():
    body = leavelater.summarize(NOW, rows(30, None, 20))
    assert body["departures"][1]["drive_min"] is None
    assert body["best"]["saving_min"] == 10


def test_plan_without_routing_is_none(monkeypatch):
    async def none(*a, **k):
        return None
    monkeypatch.setattr(leavelater.tomtom_feed, "route_times", none)
    assert asyncio.run(leavelater.plan(None, (37.442, -122.143), (37.39, -122.08))) is None


def test_endpoint(monkeypatch):
    calls = []

    async def fake(client, origin, dest, depart_at=None, **k):
        calls.append(depart_at)
        return {"travel_s": 1800 if depart_at else 2400, "delay_s": 60}

    monkeypatch.setattr(leavelater.tomtom_feed, "route_times", fake)
    c = TestClient(demo_app.app)
    r = c.get("/api/leave-later", params={"from": "37.442,-122.143", "to": "37.39,-122.08"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"checked_at", "departures", "best", "reason"}
    assert body["best"]["saving_min"] == 10
    assert calls[0] is None and len(calls) == len(body["departures"])
    assert c.get("/api/leave-later", params={"from": "x", "to": "1,2"}).status_code == 400
    assert c.get("/api/leave-later", params={"from": "1,2", "to": "1,2",
                                             "step": "7"}).status_code == 400


def test_endpoint_unavailable(monkeypatch):
    async def none(*a, **k):
        return None
    monkeypatch.setattr(leavelater.tomtom_feed, "route_times", none)
    r = TestClient(demo_app.app).get("/api/leave-later",
                                     params={"from": "37.442,-122.143", "to": "37.39,-122.08"})
    assert r.status_code == 503 and r.json()["error"]
