"""Event lifecycle archiving: appear/clear diffing across cycles."""

import pytest

from ca_roads_demo import archive


class FakeBq:
    def __init__(self):
        self.rows = []

    def insert_rows_json(self, table, rows):
        self.rows.extend((table, r) for r in rows)
        return []


@pytest.fixture
def bq(monkeypatch):
    fake = FakeBq()
    monkeypatch.setattr(archive, "_client", fake)
    monkeypatch.setattr(archive, "ENABLED", True)
    archive._seen.clear()
    return fake


EV = {"id": "chp:1", "kind": "incident", "lat": 37.3, "lon": -121.9,
      "title": "Collision", "body": "US-101 near San Jose",
      "meta": "CHP call logged 9:14 AM"}


async def test_appear_then_clear_lifecycle(bq):
    out = await archive.observe([EV])
    assert out["archived"] == 1
    table, row = bq.rows[0]
    assert table.endswith("events.event_log")
    assert row["phase"] == "appear" and row["event_id"] == "chp:1"
    assert "US-101" in row["detail"] and "9:14 AM" in row["detail"]

    # Same event again: no new rows.
    out = await archive.observe([EV])
    assert out["archived"] == 0

    # Event gone: one clear row carrying the original first_seen.
    out = await archive.observe([])
    assert out["archived"] == 1
    _, clear = bq.rows[-1]
    assert clear["phase"] == "clear"
    assert clear["first_seen"] == bq.rows[0][1]["first_seen"]
    # The clear row keeps the appear-time kind; deriving it from the id
    # prefix ("chp:") once split one event across two kind vocabularies.
    assert clear["kind"] == "incident"

    # Reappearance archives again (re-opened incident).
    out = await archive.observe([EV])
    assert out["archived"] == 1


async def test_archive_failure_never_raises(bq, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bq down")

    monkeypatch.setattr(bq, "insert_rows_json", boom)
    out = await archive.observe([EV])
    assert out["archived"] == 0 and out["failed"] == 1
