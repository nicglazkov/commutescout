"""Per-user upstream sessions on the Waze relay.

The lifecycle (made on the first request, reused, retired when idle, capped),
the account pool that makes the cap real, and the endpoint that falls back to
the shared feed instead of refusing. Nothing here talks to Waze or to Google:
the session clients are mock transports that fail any call, and the token
check is stubbed.
"""

from __future__ import annotations

import time

import auth
import httpx
import pytest
import server as relay
import sessions as sessions_module
from sessions import AccountPool, UserSessions
from store import Store
from waze.cache import AlertQueryResult, WazeAlert
from waze.device import DeviceIdentity
from waze.session import Credentials
from waze.source import RegistrationBudget, WazeSource

LA = (34.05, -118.25)
KEY = "abc123def456abc123def456"


def _no_network(_: httpx.Request) -> httpx.Response:
    raise AssertionError("a unit test must never call out")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(_no_network))


def _registry(clock, **kwargs) -> UserSessions:
    return UserSessions(client_factory=_client, now=lambda: clock[0], **kwargs)


def _alert(uuid="abc-123", *, lat=LA[0], lon=LA[1], pub_s=None) -> WazeAlert:
    return WazeAlert(uuid, 42, "POLICE", "POLICE_VISIBLE", lon, lat, 270,
                     int((pub_s or time.time() - 60) * 1000), 3, "I-110 N", "Los Angeles")


def _store() -> Store:
    source = WazeSource(_client())
    return Store(source, bbox=relay.BBOX, refresh_s=60)


# ------------------------------------------------------------- lifecycle


async def test_a_session_is_made_on_the_first_request_and_reused_after():
    clock = [1000.0]
    users = _registry(clock)
    first = await users.get(KEY)
    assert first is not None
    assert len(users) == 1
    clock[0] += 5
    again = await users.get(KEY)
    assert again is first, "the same person keeps the same session"
    assert len(users) == 1
    assert again.idle_s() == 0.0, "asking again keeps it alive"
    await users.close_all()


async def test_an_idle_session_is_retired():
    clock = [1000.0]
    users = _registry(clock, idle_s=600.0)
    session = await users.get(KEY)
    clock[0] += 599
    assert await users.get(KEY) is session
    clock[0] += 601                                  # idle past the timeout
    assert await users.expire_idle() == [KEY]
    assert len(users) == 0
    fresh = await users.get(KEY)
    assert fresh is not session, "coming back gets a new session"
    await users.close_all()


async def test_the_cap_is_a_cap_and_the_caller_falls_back():
    clock = [1000.0]
    users = _registry(clock, max_concurrent=2)
    assert await users.get("one") is not None
    assert await users.get("two") is not None
    assert await users.get("three") is None, "full means fall back, not fail"
    assert len(users) == 2
    # Somebody leaving makes room for the next person.
    clock[0] += 601
    await users.expire_idle()
    assert await users.get("three") is not None
    await users.close_all()


async def test_an_account_is_handed_back_and_lent_out_again_not_minted_again():
    clock = [1000.0]
    users = _registry(clock, max_concurrent=1)
    session = await users.get("one")
    # Pretend the upstream minted an account for this session.
    session.source._credentials = Credentials("community-1", "secret-1")
    session.source._device = DeviceIdentity.random()
    clock[0] += 601
    await users.expire_idle()
    assert users.pool.free == 1
    nextcomer = await users.get("two")
    assert nextcomer.source.registered, "the next person gets the freed account"
    assert nextcomer.source.account()[0] == Credentials("community-1", "secret-1")
    assert users.pool.free == 0
    await users.close_all()


async def test_every_session_shares_one_day_of_account_minting():
    clock = [1000.0]
    budget = RegistrationBudget(limit=3)
    users = _registry(clock, max_concurrent=5, budget=budget)
    sessions = [await users.get(f"user-{i}") for i in range(3)]
    assert all(s is not None for s in sessions)
    assert all(s.source.budget is budget for s in sessions), \
        "one allowance for the process, not one apiece"
    # Three mintings exhaust the day for everyone at once.
    for _ in range(3):
        budget.record(time.time())
    assert not budget.allowed(time.time())
    assert not sessions[0].source._can_register_today()
    await users.close_all()


def test_the_pool_lends_one_account_at_a_time():
    pool = AccountPool()
    assert pool.take() == (None, None)
    credentials, device = Credentials("c", "s"), DeviceIdentity.random()
    pool.give_back(credentials, device)
    assert pool.free == 1
    assert pool.take() == (credentials, device)
    assert pool.free == 0, "an account out on loan is not in the pool"


# --------------------------------------------------------------- refresh


async def test_a_cold_cache_refreshes_and_serves_nothing_until_it_does():
    clock = [1000.0]
    users = _registry(clock)
    session = await users.get(KEY)
    asked = []

    async def fake_refresh(lat, lon, radius_m):
        asked.append((lat, lon, round(radius_m)))
        return 0

    session.source.refresh = fake_refresh
    assert session.alerts(*LA, 25_000, _store().to_record) == []
    assert session.trigger_refresh_if_stale(*LA, 25_000) is True
    await session._task
    assert asked == [(LA[0], LA[1], 25_000)]
    assert session.servable(*LA)
    await users.close_all()


async def test_a_fresh_cache_is_left_alone_and_a_stale_one_is_not():
    clock = [1000.0]
    users = _registry(clock)
    session = await users.get(KEY)

    async def fake_refresh(lat, lon, radius_m):
        return 0

    session.source.refresh = fake_refresh
    session.trigger_refresh_if_stale(*LA, 25_000)
    await session._task
    assert session.trigger_refresh_if_stale(*LA, 25_000) is False, "still fresh"
    clock[0] += 13                                   # past the twelve-second cache
    assert session.trigger_refresh_if_stale(*LA, 25_000) is True
    await session._task
    await users.close_all()


async def test_moving_far_enough_refreshes_and_moving_a_long_way_discards():
    clock = [1000.0]
    users = _registry(clock)
    session = await users.get(KEY)

    async def fake_refresh(lat, lon, radius_m):
        return 0

    session.source.refresh = fake_refresh
    session.source.cache.submit(AlertQueryResult([_alert()], []))
    session.trigger_refresh_if_stale(*LA, 25_000)
    await session._task
    assert len(session.source.cache) == 1

    # Five kilometres down the road: refresh, keep what is cached.
    assert session.moved_km(34.095, -118.25) > 4.0
    assert session.trigger_refresh_if_stale(34.095, -118.25, 25_000) is True
    await session._task
    assert len(session.source.cache) == 1

    # The other end of the state: that is a new place, not a drive.
    assert session.moved_km(37.77, -122.42) > 25.0
    assert session.servable(37.77, -122.42) is False
    assert session.trigger_refresh_if_stale(37.77, -122.42, 25_000) is True
    await session._task
    assert len(session.source.cache) == 0, "the old city is thrown away"
    await users.close_all()


async def test_a_cache_nobody_could_refresh_stops_being_served():
    clock = [1000.0]
    users = _registry(clock)
    session = await users.get(KEY)

    async def fake_refresh(lat, lon, radius_m):
        return 0

    session.source.refresh = fake_refresh
    session.trigger_refresh_if_stale(*LA, 25_000)
    await session._task
    assert session.servable(*LA)
    clock[0] += 601                                  # ten minutes with no refresh
    assert session.servable(*LA) is False
    await users.close_all()


async def test_a_failed_refresh_is_recorded_and_does_not_wedge_the_session():
    clock = [1000.0]
    users = _registry(clock)
    session = await users.get(KEY)

    async def boom(lat, lon, radius_m):
        raise RuntimeError("upstream said no")

    session.source.refresh = boom
    session.trigger_refresh_if_stale(*LA, 25_000)
    await session._task
    assert session.source.last_error == "RuntimeError: upstream said no"
    assert session._refreshing is False, "the next request may try again"
    await users.close_all()


async def test_alerts_come_back_nearest_first_and_clipped_to_the_radius():
    clock = [1000.0]
    users = _registry(clock)
    session = await users.get(KEY)

    async def fake_refresh(lat, lon, radius_m):
        return 0

    session.source.refresh = fake_refresh
    session.source.cache.submit(AlertQueryResult(
        [_alert("far", lat=LA[0] + 0.2), _alert("close")], []))
    session.trigger_refresh_if_stale(*LA, 25_000)
    await session._task
    store = _store()
    assert [a["id"] for a in session.alerts(*LA, 50_000, store.to_record)] == \
        ["wz:close", "wz:far"]
    assert [a["id"] for a in session.alerts(*LA, 5_000, store.to_record)] == ["wz:close"]
    await users.close_all()


def test_a_position_is_snapped_before_it_is_used():
    assert sessions_module.snap(34.0521968) == 34.05
    assert sessions_module.snap(-118.2436849) == -118.24


# -------------------------------------------------------------- endpoint


def _app_client(store, users=None, *, enabled=True) -> httpx.AsyncClient:
    relay.store = store
    relay.users = users
    relay.USER_SESSIONS = enabled
    relay.auth_client = _client()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=relay.app),
                             base_url="http://localhost")


async def test_the_endpoint_is_absent_until_the_flag_is_on(monkeypatch):
    async with _app_client(_store(), enabled=False) as client:
        response = await client.get("/flare/v1/me/alerts",
                                    params={"lat": LA[0], "lon": LA[1], "r": 25_000})
    assert response.status_code == 404
    # ...and the handshake says nothing about it, so an app feature-detects off.
    assert "extensions" not in relay.PLUGIN


def test_turning_the_flag_on_advertises_the_extension(monkeypatch):
    """The handshake is how an app finds the mode, so prove both states."""
    import importlib

    assert "extensions" not in relay.PLUGIN
    monkeypatch.setenv("WAZE_USER_SESSIONS", "1")
    monkeypatch.setenv("WAZE_USER_SESSIONS_MAX", "3")
    monkeypatch.setenv("WAZE_USER_IDLE_S", "900")
    try:
        importlib.reload(relay)
        assert relay.USER_SESSIONS is True
        assert relay.PLUGIN["extensions"]["user_sessions"] == {
            "path": "/flare/v1/me/alerts", "auth": "firebase",
            "idle_s": 900, "max_concurrent": 3}
        # Everything a caller already relied on is still exactly as it was.
        assert relay.PLUGIN["auth"] == "none"
        assert relay.PLUGIN["capabilities"]["report"] is False
        assert "/flare/v1/alerts" in [r.path for r in relay.app.routes]
    finally:
        monkeypatch.undo()
        importlib.reload(relay)
    assert relay.USER_SESSIONS is False
    assert "extensions" not in relay.PLUGIN


async def test_an_unsigned_caller_is_refused_and_pointed_at_the_shared_feed(monkeypatch):
    monkeypatch.setattr(auth, "verify", _verify_none)
    clock = [1000.0]
    async with _app_client(_store(), _registry(clock)) as client:
        response = await client.get("/flare/v1/me/alerts",
                                    params={"lat": LA[0], "lon": LA[1], "r": 25_000})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "/flare/v1/alerts" in response.json()["error"]["hint"]


async def test_a_signed_in_caller_gets_their_own_session(monkeypatch):
    monkeypatch.setattr(auth, "verify", _verify_key)
    clock = [1000.0]
    users = _registry(clock)
    async with _app_client(_store(), users) as client:
        response = await client.get(
            "/flare/v1/me/alerts", headers={"Authorization": "Bearer token"},
            params={"lat": LA[0], "lon": LA[1], "r": 25_000})
    body = response.json()
    assert response.status_code == 200
    assert body["session"] == "user"
    assert body["alerts"] == []          # cold, and it does not block to fill
    assert len(users) == 1
    await users.close_all()


async def test_a_full_relay_serves_the_shared_feed_and_says_so(monkeypatch):
    monkeypatch.setattr(auth, "verify", _verify_key)
    clock = [1000.0]
    users = _registry(clock, max_concurrent=1)
    await users.get("somebody-else")     # the only slot is taken
    store = _store()
    store.source.cache.submit(AlertQueryResult([_alert()], []))
    store.source.last_ok = store._now()
    async with _app_client(store, users) as client:
        response = await client.get(
            "/flare/v1/me/alerts", headers={"Authorization": "Bearer token"},
            params={"lat": LA[0], "lon": LA[1], "r": 25_000})
    body = response.json()
    assert response.status_code == 200
    assert body["session"] == "shared"
    assert [a["id"] for a in body["alerts"]] == ["wz:abc-123"]
    await users.close_all()


async def test_the_flag_on_without_a_registry_falls_back_rather_than_erroring(monkeypatch):
    monkeypatch.setattr(auth, "verify", _verify_key)
    store = _store()
    store.source.cache.submit(AlertQueryResult([_alert()], []))
    store.source.last_ok = store._now()
    async with _app_client(store, None) as client:     # registry never came up
        response = await client.get(
            "/flare/v1/me/alerts", headers={"Authorization": "Bearer token"},
            params={"lat": LA[0], "lon": LA[1], "r": 25_000})
    assert response.status_code == 200
    assert response.json()["session"] == "shared"


async def test_a_signed_in_caller_outside_coverage_is_refused(monkeypatch):
    monkeypatch.setattr(auth, "verify", _verify_key)
    clock = [1000.0]
    users = _registry(clock)
    async with _app_client(_store(), users) as client:
        response = await client.get(
            "/flare/v1/me/alerts", headers={"Authorization": "Bearer token"},
            params={"lat": 51.5, "lon": -0.12, "r": 25_000})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "outside_coverage"
    assert len(users) == 0, "a refusal opens nothing"
    await users.close_all()


async def test_the_shared_endpoint_is_untouched_by_any_of_this(monkeypatch):
    store = _store()
    store.source.cache.submit(AlertQueryResult([_alert()], []))
    store.source.last_ok = store._now()
    async with _app_client(store, _registry([1000.0])) as client:
        response = await client.get("/flare/v1/alerts",
                                    params={"lat": LA[0], "lon": LA[1], "r": 25_000})
    body = response.json()
    assert response.status_code == 200
    assert "session" not in body, "the shared feed's shape does not change"
    assert [a["id"] for a in body["alerts"]] == ["wz:abc-123"]


async def _verify_key(token, client):
    return KEY if token else None


async def _verify_none(token, client):
    return None


def test_a_session_key_is_opaque_and_stable():
    first = auth.session_key("firebase-uid-12345")
    assert first == auth.session_key("firebase-uid-12345")
    assert first != auth.session_key("firebase-uid-54321")
    assert len(first) == 24
    assert "firebase-uid-12345" not in first


def test_a_bearer_header_is_read_and_anything_else_is_not():
    assert auth.bearer("Bearer abc") == "abc"
    assert auth.bearer("bearer abc") == ""
    assert auth.bearer("abc") == ""
    assert auth.bearer(None) == ""


@pytest.fixture(autouse=True)
def _restore_module_state():
    before = (relay.store, relay.users, relay.USER_SESSIONS, relay.auth_client)
    yield
    relay.store, relay.users, relay.USER_SESSIONS, relay.auth_client = before
