"""Alert settings from the watches screen: quiet hours with one summary,
"tell me when it clears", account-wide push and email switches, the
per-watch live status line, and a checker that never recreates a watch
deleted mid-cycle."""

from __future__ import annotations

from datetime import datetime

import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from tests.test_watch import EVENT, auth, checker, seed_watch, store  # noqa: F401

from ca_roads_demo import watch

pytestmark = pytest.mark.asyncio

QUIET = {"enabled": True, "start": "22:00", "end": "06:00",
         "tz": "America/Los_Angeles", "summary": True}


def _app():
    return Starlette(routes=[
        Route("/api/watch/me", watch.api_watch_me),
        Route("/api/watch/prefs", watch.api_watch_prefs, methods=["POST"]),
    ])


async def test_prefs_take_alert_settings(store):  # noqa: F811
    c = TestClient(_app())
    r = c.post("/api/watch/prefs", headers=auth(),
               json={"notify_clears": True, "alerts_email": False,
                     "quiet_hours": {"enabled": True, "start": "22:00", "end": "6:00"}})
    assert r.status_code == 200, r.text
    prefs = r.json()["prefs"]
    assert prefs["notify_clears"] is True and prefs["alerts_email"] is False
    assert prefs["quiet_hours"] == {**QUIET, "end": "06:00"}
    # Units still work alone, and keep the rest.
    r = c.post("/api/watch/prefs", json={"units": "km"}, headers=auth())
    assert r.json()["prefs"]["units"] == "km" and r.json()["prefs"]["notify_clears"] is True
    for bad in ({"notify_clears": "yes"}, {"quiet_hours": {"start": "25:00"}},
                {"quiet_hours": {"start": "06:00", "end": "06:00"}},
                {"quiet_hours": {"tz": "Mars/Base"}}, {"quiet_hours": "late"}, {}):
        assert c.post("/api/watch/prefs", json=bad, headers=auth()).status_code == 400, bad


def at(hh, mm=0):
    return datetime(2026, 10, 29, hh, mm, tzinfo=watch.ZoneInfo("America/Los_Angeles")).timestamp()


def test_quiet_hours_window():
    prefs = {"quiet_hours": QUIET}
    assert watch.in_quiet_hours(prefs, at(23))
    assert watch.in_quiet_hours(prefs, at(5, 59))
    assert not watch.in_quiet_hours(prefs, at(6))
    assert not watch.in_quiet_hours(prefs, at(12))
    day = {"quiet_hours": {**QUIET, "start": "09:00", "end": "17:00"}}
    assert watch.in_quiet_hours(day, at(12)) and not watch.in_quiet_hours(day, at(18))
    assert not watch.in_quiet_hours({"quiet_hours": {**QUIET, "enabled": False}}, at(23))
    assert not watch.in_quiet_hours({}, at(23))


def test_live_status_line():
    now = at(8).__int__()
    s = watch.live_status([], None, now)
    assert s["count"] == 0 and s["quiet_since"] and s["top"] is None
    assert watch.live_status([], s, now + 600)["quiet_since"] == s["quiet_since"]
    busy = watch.live_status([EVENT, {**EVENT, "id": "chain:1", "kind": "chain",
                                      "title": "Chains required"}], s, now)
    assert busy["count"] == 2 and busy["by_kind"] == {"incident": 1, "chain": 1}
    assert busy["top"]["title"] == "Chains required" and busy["quiet_since"] is None


async def _ready(store, prefs):  # noqa: F811
    wid = await seed_watch(store)
    await store.set_seen(wid, {"chp:0"})
    await store.upsert_user("sam", {"prefs": prefs})
    return wid


async def test_quiet_hours_hold_then_one_summary(checker, monkeypatch):  # noqa: F811
    store, events, pushes = checker  # noqa: F811
    wid = await _ready(store, {"quiet_hours": QUIET})
    monkeypatch.setattr(watch.time, "time", lambda: at(23))
    events.append(EVENT)
    events.append({**EVENT, "id": "chp:2", "title": "Hazard"})
    await watch.run_check_cycle()
    assert pushes == []
    assert len(store.watches[wid]["quiet_held"]) == 2
    monkeypatch.setattr(watch.time, "time", lambda: at(6, 5))
    await watch.run_check_cycle()
    assert len(pushes) == 1
    assert pushes[0][1]["title"] == "Home: 2 alerts during quiet hours"
    assert pushes[0][1]["event"]["kind"] == "summary"
    assert store.watches[wid]["quiet_held"] == []
    await watch.run_check_cycle()
    assert len(pushes) == 1          # held events are not alerted again
    # /api/watch/me hides the checker's bookkeeping.
    me = TestClient(_app()).get("/api/watch/me", headers=auth()).json()
    assert "quiet_held" not in me["watches"][0] and "live" in me["watches"][0]


async def test_watch_can_opt_out_of_quiet_hours(checker, monkeypatch):  # noqa: F811
    store, events, pushes = checker  # noqa: F811
    wid = await _ready(store, {"quiet_hours": QUIET})
    await store.update_watch(wid, {"quiet_hours": False})
    monkeypatch.setattr(watch.time, "time", lambda: at(23))
    events.append(EVENT)
    await watch.run_check_cycle()
    assert len(pushes) == 1


async def test_tell_me_when_it_clears(checker):  # noqa: F811
    store, events, pushes = checker  # noqa: F811
    wid = await _ready(store, {"notify_clears": True})
    events.append(EVENT)
    await watch.run_check_cycle()
    assert len(pushes) == 1 and "chp:1" in store.watches[wid]["alerted"]
    events.clear()
    await watch.run_check_cycle()        # one miss could be a feed blink
    assert len(pushes) == 1
    await watch.run_check_cycle()
    assert len(pushes) == 2
    assert pushes[1][1]["title"] == "Home: cleared"
    assert pushes[1][1]["event"]["status"] == "cleared"
    assert store.watches[wid]["alerted"] == {}
    await watch.run_check_cycle()
    assert len(pushes) == 2


async def test_no_clear_follow_up_unless_asked(checker):  # noqa: F811
    store, events, pushes = checker  # noqa: F811
    await _ready(store, {})
    events.append(EVENT)
    await watch.run_check_cycle()
    events.clear()
    for _ in range(3):
        await watch.run_check_cycle()
    assert len(pushes) == 1


async def test_account_push_switch(checker):  # noqa: F811
    store, events, pushes = checker  # noqa: F811
    await _ready(store, {"alerts_push": False})
    events.append(EVENT)
    await watch.run_check_cycle()
    assert pushes == []


async def test_watch_deleted_mid_cycle_is_not_recreated(checker, monkeypatch):  # noqa: F811
    store, events, pushes = checker  # noqa: F811
    wid = await _ready(store, {"notify_clears": True})
    events.append(EVENT)
    real_set_seen = store.set_seen

    async def delete_then_set(watch_id, seen):
        # The user deletes the watch while the checker is mid-way.
        store.watches.pop(watch_id, None)
        await real_set_seen(watch_id, seen)

    monkeypatch.setattr(store, "set_seen", delete_then_set)
    stats = await watch.run_check_cycle()
    assert wid not in store.watches
    assert wid not in store.seen          # no orphaned seen state either
    assert not stats.get("errors")


async def test_edit_racing_a_delete_is_404(store):  # noqa: F811
    wid = await seed_watch(store)
    real_get = store.get_watch

    async def get_then_delete(watch_id):
        w = await real_get(watch_id)
        store.watches.pop(watch_id, None)     # deleted right after the read
        return w

    store.get_watch = get_then_delete
    c = TestClient(Starlette(routes=[
        Route("/api/watch/{watch_id}", watch.api_watch_update, methods=["PATCH"])]))
    r = c.patch(f"/api/watch/{wid}", json={"name": "Renamed"}, headers=auth())
    assert r.status_code == 404
    assert wid not in store.watches
