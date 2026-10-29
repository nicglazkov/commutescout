"""OpenStreetMap lane-count lookup: way choice, cache and queue."""

from __future__ import annotations

import asyncio

import pytest

from ca_roads_demo import lanecount as lc

LAT, LON = 37.442, -122.143


def way(tags, pts, way_id=1):
    return {"type": "way", "id": way_id, "tags": tags,
            "geometry": [{"lat": a, "lon": b} for a, b in pts]}


# Two carriageways of a north-south freeway, 30 m either side of the point.
NB = way({"highway": "motorway", "oneway": "yes", "lanes": "4",
          "hov:lanes": "designated|yes|yes|yes"},
         [(LAT - 0.002, LON + 0.0003), (LAT + 0.002, LON + 0.0003)], 1)
SB = way({"highway": "motorway", "oneway": "yes", "lanes": "3"},
         [(LAT + 0.002, LON - 0.0003), (LAT - 0.002, LON - 0.0003)], 2)
RAMP = way({"highway": "motorway_link", "oneway": "yes", "lanes": "1"},
           [(LAT, LON), (LAT + 0.001, LON + 0.001)], 3)
FRONTAGE = way({"highway": "secondary", "lanes": "2", "lanes:forward": "1",
                "lanes:backward": "1"},
               [(LAT - 0.002, LON), (LAT + 0.002, LON)], 4)


@pytest.fixture(autouse=True)
def clean():
    lc._cache.clear()
    lc._queue.clear()
    yield
    lc._cache.clear()
    lc._queue.clear()


def test_pick_matches_direction_of_travel():
    assert lc.pick([NB, SB, RAMP], LAT, LON, "NB") == (4, {1: "hov"})
    assert lc.pick([NB, SB, RAMP], LAT, LON, "southbound") == (3, {})


def test_pick_freeway_beats_closer_frontage_road():
    assert lc.pick([FRONTAGE, SB], LAT, LON, "S") == (3, {})


def test_pick_two_way_road_uses_its_side():
    assert lc.pick([FRONTAGE], LAT, LON, "N") == (1, {})
    both = way({"highway": "primary", "lanes": "4"}, [(LAT - 0.002, LON), (LAT + 0.002, LON)])
    assert lc.pick([both], LAT, LON, "S") == (2, {})
    odd = way({"highway": "primary", "lanes": "3"}, [(LAT - 0.002, LON), (LAT + 0.002, LON)])
    assert lc.pick([odd], LAT, LON, "S") is None
    # Without a direction a two-way road is ambiguous.
    assert lc.pick([both], LAT, LON, None) is None


def test_pick_ignores_far_roads_links_and_missing_tags():
    far = way({"highway": "motorway", "oneway": "yes", "lanes": "5"},
              [(LAT - 0.002, LON + 0.003), (LAT + 0.002, LON + 0.003)])
    bare = way({"highway": "motorway", "oneway": "yes"},
               [(LAT - 0.002, LON), (LAT + 0.002, LON)])
    assert lc.pick([far, RAMP, bare], LAT, LON, "N") is None
    assert lc.pick([], LAT, LON, "N") is None
    assert lc.pick([way({"highway": "motorway"}, [])], LAT, LON, "N") is None


def test_pick_reversed_oneway():
    rev = way({"highway": "trunk", "oneway": "-1", "lanes": "2"},
              [(LAT + 0.002, LON), (LAT - 0.002, LON)])
    assert lc.pick([rev], LAT, LON, "N") == (2, {})
    assert lc.pick([rev], LAT, LON, "S") is None


def test_heading_letter():
    assert lc.heading_letter("NB") == "N"
    assert lc.heading_letter("westbound") == "W"
    assert lc.heading_letter("") is None
    assert lc.heading_letter(None) is None
    assert lc.heading_letter("both") is None


def test_known_and_want():
    assert lc.known(LAT, LON, "N") is None
    lc.want(LAT, LON, "N")
    lc.want(LAT + 0.0001, LON, "NB")   # same rounded key: queued once
    assert len(lc._queue) == 1
    lc._store(lc._key(LAT, LON, "N"), (4, {}))
    assert lc.known(LAT, LON, "northbound") == (4, {})
    assert lc.known(LAT, LON, "S") is None
    lc._queue.clear()
    lc.want(LAT, LON, "N")              # cached: nothing to do
    assert not lc._queue
    assert lc.known(None, LON) is None


def test_misses_expire_sooner(monkeypatch):
    lc._store(lc._key(LAT, LON, "N"), None)
    now = lc.time.time()
    monkeypatch.setattr(lc.time, "time", lambda: now + lc.MISS_TTL + 1)
    lc.want(LAT, LON, "N")
    assert len(lc._queue) == 1


def test_queue_is_bounded(monkeypatch):
    monkeypatch.setattr(lc, "QUEUE_MAX", 3)
    for i in range(5):
        lc.want(LAT + i * 0.01, LON)
    assert len(lc._queue) == 3


def test_query_shape():
    q = lc.query(LAT, LON)
    assert q.startswith("[out:json]")
    assert "around:150,37.44200,-122.14300" in q
    assert "out tags geom(" in q


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeClient:
    def __init__(self, resp):
        self.resp = resp
        self.calls = []

    async def post(self, url, data, headers, timeout):
        self.calls.append((url, data, headers))
        return self.resp


def test_lookup_parses_and_identifies_itself():
    client = FakeClient(FakeResp(200, {"elements": [NB, SB]}))
    assert asyncio.run(lc.lookup(client, LAT, LON, "S")) == (3, {})
    assert "commutescout.com" in client.calls[0][2]["User-Agent"]


def test_lookup_busy_raises():
    with pytest.raises(RuntimeError):
        asyncio.run(lc.lookup(FakeClient(FakeResp(429, {})), LAT, LON, "S"))


def test_worker_drains_queue_under_cap(monkeypatch):
    client = FakeClient(FakeResp(200, {"elements": [NB]}))
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) > 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(lc, "_sleep", fake_sleep)
    lc.want(LAT, LON, "N")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(lc._drain(lambda: client))
    assert lc.known(LAT, LON, "N") == (4, {1: "hov"})
    assert len(client.calls) == 1


# ---------------------------------------------------------------- layouts

def test_lcs_layout_uses_feed_count_then_lookup():
    from types import SimpleNamespace as NS
    c = NS(lanes_closed="3, 4", total_lanes=4, begin_lat=LAT, begin_lon=LON, direction="NB")
    assert lc.lcs_layout(c)["basis"] == "feed"
    c = NS(lanes_closed="2", total_lanes=None, begin_lat=LAT, begin_lon=LON, direction="NB")
    assert lc.lcs_layout(c) is None
    assert len(lc._queue) == 1           # asked the map
    lc._store(lc._key(LAT, LON, "N"), (3, {}))
    layout = lc.lcs_layout(c)
    assert layout["basis"] == "lookup"
    assert [ln["state"] for ln in layout["lanes"]] == ["open", "closed", "open"]


def test_chp_layout_waits_for_lookup():
    from types import SimpleNamespace as NS
    i = NS(id="X1", lat=LAT, lon=LON, location="Us101 N / University Ave",
           details=[("t", "[1] 2 VEHS BLKG #3 #4")])
    assert lc.chp_layout(i) is None
    assert len(lc._queue) == 1
    lc._store(lc._key(LAT, LON, "N"), (4, {}))
    layout = lc.chp_layout(i)
    assert layout["target"] == 2 and layout["basis"] == "lookup"
    quiet = NS(id="X2", lat=LAT, lon=LON, location="Us101 N", details=[("t", "[1] 1039 TOW")])
    assert lc.chp_layout(quiet) is None


def test_text_layouts_only_fill_unknown_markers():
    lc._store(lc._key(LAT, LON, "E"), (3, {}))
    fixed = {"total": 2}
    ms = [{"kind": "lane_closure", "lat": LAT, "lon": LON, "dir": "Eastbound",
           "lanes": "Right lane closed"},
          {"kind": "lane_closure", "lat": LAT, "lon": LON, "lanes": "x",
           "lane_layout": fixed},
          {"kind": "sign", "lat": LAT, "lon": LON, "lanes": "Right lane closed"}]
    lc.text_layouts(ms)
    assert [ln["n"] for ln in ms[0]["lane_layout"]["lanes"] if ln["state"] == "closed"] == [3]
    assert ms[1]["lane_layout"] is fixed
    assert "lane_layout" not in ms[2]


def test_fcm_values_are_strings():
    from ca_roads_demo import watch
    assert watch._fcm_value({"total": 2, "lanes": []}) == '{"total":2,"lanes":[]}'
    assert watch._fcm_value(3) == "3"
