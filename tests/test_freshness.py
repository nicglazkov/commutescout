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
    monkeypatch.setattr(freshness, "_strikes", {})
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
    assert freshness._state_limit("neccam:me") == freshness.CAMERA_STALE_S


def test_one_outage_is_one_error_then_warnings_then_a_recovery(caplog):
    caplog.set_level(logging.INFO, logger="ca_roads_demo.freshness")
    freshness.report({"X": "old"}, now=0)        # first strike: nothing yet
    freshness.report({"X": "old"}, now=300)      # second: reported once
    freshness.report({"X": "old"}, now=600)
    freshness.report({"X": "old"}, now=3900)     # an hour on: a reminder
    freshness.report({}, now=4200)
    lines = [(r.levelname, r.getMessage().split(":")[0]) for r in caplog.records]
    assert lines == [("ERROR", "feed stale"), ("WARNING", "feed still stale"),
                     ("INFO", "feed recovered")]


def test_a_single_failed_read_is_not_reported(caplog):
    caplog.set_level(logging.INFO, logger="ca_roads_demo.freshness")
    freshness.report({"X": "old"}, now=0)
    freshness.report({}, now=300)
    freshness.report({"X": "old"}, now=600)
    freshness.report({}, now=900)
    assert caplog.records == []
