"""A source that stops refreshing says so, once an hour, without keys."""

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from ca_roads_demo import freshness, states


class FakeRoad:
    def __init__(self, age_min: dict[str, float]):
        self.age = age_min

    def __getattr__(self, method):
        async def read():
            minutes = self.age.get(method, 1)
            return SimpleNamespace(
                data_as_of=datetime.now(UTC) - timedelta(minutes=minutes),
                error="HTTPStatusError: 500 for url 'https://x/f?key=SECRET'"
                if minutes > 60 else None)
        return read


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(freshness, "_stale_since", {})
    monkeypatch.setattr(freshness, "_last_logged", {})
    monkeypatch.setattr(states._cache, "_entries", {})
    monkeypatch.setattr(states._cache, "_errors", {})


@pytest.mark.asyncio
async def test_a_stale_california_feed_is_named_and_its_key_never_logged(monkeypatch):
    from ca_roads_mcp import server
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad({"incidents": 90}))
    stale = await freshness.find_stale()
    assert list(stale) == ["California incidents (CHP)"]
    assert "SECRET" not in stale["California incidents (CHP)"]


@pytest.mark.asyncio
async def test_cameras_are_allowed_hours_and_tolls_their_own_interval(monkeypatch):
    from ca_roads_mcp import server
    monkeypatch.setattr(server, "get_road", lambda: FakeRoad({"cameras": 180}))
    assert await freshness.find_stale() == {}
    assert freshness._state_limit("toll:cabr") >= 3 * 86400
    assert freshness._state_limit("il:all") == freshness.STATE_STALE_S


def test_stale_is_logged_once_an_hour_and_recovery_once(caplog):
    caplog.set_level(logging.INFO, logger="ca_roads_demo.freshness")
    freshness.report({"X": "old"}, now=0)
    freshness.report({"X": "old"}, now=600)
    freshness.report({"X": "old"}, now=3600)
    freshness.report({}, now=3900)
    lines = [(r.levelname, r.getMessage().split(":")[0]) for r in caplog.records]
    assert lines == [("ERROR", "feed stale"), ("ERROR", "feed stale"),
                     ("INFO", "feed recovered")]
