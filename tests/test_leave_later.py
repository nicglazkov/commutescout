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


def _fake_routes(monkeypatch, calls):
    async def fake(client, origin, dest, depart_at=None, *, charge=None, **k):
        if charge is not None and not charge():
            return None
        calls.append(depart_at)
        return {"travel_s": 1800, "delay_s": 0}
    monkeypatch.setattr(leavelater.tomtom_feed, "route_times", fake)
    monkeypatch.setattr(leavelater, "UPSTREAM", demo_app.DailyCounter())


def test_slot_count_and_trip_length_are_bounded(monkeypatch):
    calls = []
    _fake_routes(monkeypatch, calls)
    c = TestClient(demo_app.app)
    pa = "37.442,-122.143"
    # 90 minutes every 5 is 19 departures: refused before any route.
    r = c.get("/api/leave-later", params={"from": pa, "to": "37.39,-122.08",
                                          "window": "90", "step": "5"})
    assert r.status_code == 400 and "at most 10" in r.json()["error"]
    # Coast to coast is not a leave-later trip.
    r = c.get("/api/leave-later", params={"from": pa, "to": "40.71,-74.0"})
    assert r.status_code == 400
    assert calls == []
    r = c.get("/api/leave-later", params={"from": pa, "to": "37.39,-122.08",
                                          "window": "90", "step": "10"})
    assert r.status_code == 200 and len(calls) <= leavelater.MAX_SLOTS


def test_charged_per_route_not_per_request(monkeypatch):
    calls = []
    _fake_routes(monkeypatch, calls)
    monkeypatch.setitem(demo_app.PAID_PER_CLIENT_DAILY, "leavelater", 10)
    monkeypatch.setattr(demo_app, "paid_use", demo_app.DailyCounter())
    c = TestClient(demo_app.app)
    q = {"from": "37.442,-122.143", "to": "37.39,-122.08"}
    first = c.get("/api/leave-later", params=q)                 # 6 or 7 routes
    assert first.status_code == 200
    n = len(first.json()["departures"])
    second = c.get("/api/leave-later", params=q)    # only 10 - n routes left
    assert len(calls) == 10
    assert sum(d["drive_min"] is not None for d in second.json()["departures"]) == 10 - n
    assert c.get("/api/leave-later", params=q).status_code == 429   # spent


def test_cached_departures_cost_nothing(monkeypatch):
    monkeypatch.setattr(leavelater.tomtom_feed, "route_cached", lambda *a, **k: True)
    assert leavelater.uncached((1, 2), (1, 3), [None, NOW]) == 0
    monkeypatch.setattr(leavelater.tomtom_feed, "route_cached", lambda *a, **k: False)
    assert leavelater.uncached((1, 2), (1, 3), [None, NOW]) == 2


def test_own_share_of_the_routing_budget(monkeypatch):
    monkeypatch.setattr(leavelater, "UPSTREAM", demo_app.DailyCounter())
    monkeypatch.setattr(leavelater, "DAILY_ROUTES", 2)
    charge = leavelater.make_charge(lambda: True)
    assert charge() and charge() and not charge()
    assert charge.refused == 1


def test_route_times_charges_only_real_misses(monkeypatch):
    from ca_roads.feeds import tomtom

    class Resp:
        status_code = 200

        def json(self):
            return {"routes": [{"summary": {"travelTimeInSeconds": 600}}]}

    class Client:
        n = 0

        async def get(self, *a, **k):
            Client.n += 1
            return Resp()

    monkeypatch.setattr(tomtom, "api_key", lambda: "k")
    monkeypatch.setattr(tomtom, "_route_cache", {})
    paid = []
    ok = lambda: paid.append(1) or True  # noqa: E731
    run = lambda c: asyncio.run(tomtom.route_times(  # noqa: E731
        Client(), (37.442, -122.143), (37.39, -122.08), "2026-10-29T16:00:00+00:00", charge=c))
    assert run(ok)["travel_s"] == 600 and paid == [1]
    assert run(ok)["travel_s"] == 600 and paid == [1]     # cache hit: free
    monkeypatch.setattr(tomtom, "_route_cache", {})
    assert run(lambda: False) is None and Client.n == 1   # refused: no call


def test_cache_expiring_between_check_and_plan_is_still_paid(monkeypatch):
    """The pre-check saw every slot cached, then the entries expired:
    each real call is charged, and calls past the cap never happen."""
    upstream = []

    async def route_times(client, origin, dest, depart_at=None, *, charge=None, **k):
        if charge is not None and not charge():   # a miss, as in tomtom.route_times
            return None
        upstream.append(depart_at)
        return {"travel_s": 1800, "delay_s": 0}

    monkeypatch.setattr(leavelater.tomtom_feed, "route_times", route_times)
    monkeypatch.setattr(leavelater.tomtom_feed, "route_cached", lambda *a, **k: True)
    monkeypatch.setitem(demo_app.PAID_PER_CLIENT_DAILY, "leavelater", 3)
    monkeypatch.setattr(demo_app, "paid_use", demo_app.DailyCounter())
    monkeypatch.setattr(leavelater, "UPSTREAM", demo_app.DailyCounter())
    r = TestClient(demo_app.app).get("/api/leave-later",
                                     params={"from": "37.442,-122.143", "to": "37.39,-122.08"})
    assert len(upstream) == 3                     # never more than were paid for
    assert r.status_code == 200
    assert sum(d["drive_min"] is not None for d in r.json()["departures"]) == 3
