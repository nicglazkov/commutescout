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


async def test_update_rows_carry_only_new_timeline_entries(bq):
    import json

    ev = dict(EV)
    ev["payload"] = {"details": [["12:37AM", "[1] 2 VEH TC"]],
                     "units": [], "location_desc": "EB AT THE ONRAMP"}
    out = await archive.observe([ev])
    assert out["archived"] == 1
    _, appear = bq.rows[0]
    payload = json.loads(appear["payload"])
    assert payload["details"] == [["12:37AM", "[1] 2 VEH TC"]]
    assert payload["state"]["location_desc"] == "EB AT THE ONRAMP"

    # Same state: nothing new to write.
    out = await archive.observe([ev])
    assert out["archived"] == 0

    # A new dispatch entry appears: one update row with ONLY the new line.
    ev2 = dict(ev)
    ev2["payload"] = {"details": [["12:37AM", "[1] 2 VEH TC"],
                                  ["12:51AM", "[18] X2 TOYT COA / HOND SUV"]],
                      "units": [], "location_desc": "EB AT THE ONRAMP"}
    out = await archive.observe([ev2])
    assert out["archived"] == 1
    _, upd = bq.rows[-1]
    assert upd["phase"] == "update"
    assert upd["first_seen"] == appear["first_seen"]
    assert json.loads(upd["payload"])["details"] == [
        ["12:51AM", "[18] X2 TOYT COA / HOND SUV"]]

    # A problem-type change (title) is also an update.
    ev3 = dict(ev2)
    ev3["title"] = "1181-Trfc Collision-Minor Inj"
    out = await archive.observe([ev3])
    assert out["archived"] == 1
    assert bq.rows[-1][1]["phase"] == "update"

    # Clear still keeps the appear-time kind.
    out = await archive.observe([])
    assert bq.rows[-1][1]["phase"] == "clear"
    assert bq.rows[-1][1]["kind"] == "incident"


async def test_archive_failure_never_raises(bq, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bq down")

    monkeypatch.setattr(bq, "insert_rows_json", boom)
    out = await archive.observe([EV])
    assert out["archived"] == 0 and out["failed"] == 1
