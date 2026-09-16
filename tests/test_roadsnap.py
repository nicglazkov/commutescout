"""Road snapper: quality gates, caching, and marker application."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from ca_roads_demo import roadsnap
from test_valhalla import encode_polyline6

ROUTE_RE = r".*api\.stadiamaps\.com/route/v1.*"


def setup_function(_fn):
    roadsnap._mem.clear()
    roadsnap._queue.clear()
    roadsnap._queued.clear()
    roadsnap._pairs.clear()
    roadsnap._tries.clear()
    roadsnap._loaded = False


@pytest.fixture(autouse=True)
def _routing_key(monkeypatch):
    monkeypatch.setenv("STADIA_API_KEY", "test-key")


def _trip(points, km, maneuvers=None):
    """Valhalla response: points are [lat, lon], length in kilometers."""
    leg = {"shape": encode_polyline6(points)}
    if maneuvers is not None:
        leg["maneuvers"] = maneuvers
    return {"trip": {"legs": [leg],
                     "summary": {"length": km, "time": 600}}}


async def test_snap_returns_road_shape():
    points = [[37.3, -121.9], [37.31, -121.91], [37.33, -121.92]]
    with respx.mock:
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(200, json=_trip(points, 4.0)))
        async with httpx.AsyncClient() as client:
            path = await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)
    assert path[0] == [37.3, -121.9] and path[-1] == [37.33, -121.92]


async def test_snap_rejects_absurd_detours():
    # Straight distance ~3.7 km but the route is 40 km: endpoints are
    # on different roads; the gate refuses to draw a wrong shape.
    points = [[37.3, -121.9], [37.33, -121.92]]
    with respx.mock:
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(200, json=_trip(points, 40.0)))
        async with httpx.AsyncClient() as client:
            path = await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)
    assert path is None


async def test_snap_skips_tiny_and_huge_pairs():
    async with httpx.AsyncClient() as client:
        assert await roadsnap._snap(client, 37.3, -121.9,
                                    37.3001, -121.9001) is None
        assert await roadsnap._snap(client, 37.3, -121.9,
                                    47.0, -100.0) is None


async def test_snap_without_key_raises_not_tombstones(monkeypatch):
    """A keyless process must never write pairs off as unroutable: the
    drain loop gates on _ready() and a direct call raises (the generic
    requeue path) instead of returning the cached-forever None."""
    monkeypatch.delenv("STADIA_API_KEY", raising=False)
    assert roadsnap._ready() is False
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError):
            await roadsnap._snap(client, 37.3, -121.9, 37.33, -121.92)


async def test_snap_toll_sends_heading_and_validates():
    points = [[37.30, -121.90], [37.31, -121.91], [37.33, -121.92]]
    maneuvers = [{"street_names": ["US 101"], "length": 4.0}]
    with respx.mock:
        route = respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(
                200, json=_trip(points, 4.0, maneuvers)))
        async with httpx.AsyncClient() as client:
            got = await roadsnap._snap_toll(
                client, 37.30, -121.90, 37.33, -121.92, 330.0, "101")
    body = route.calls[0].request.read()
    assert b'"heading"' in body and b'"heading_tolerance"' in body
    assert b'"radius"' in body
    assert got["path"][0] == [37.3, -121.9]
    assert got["a"] == [37.3, -121.9] and got["b"] == [37.33, -121.92]


async def test_snap_toll_rejects_off_route_legs():
    points = [[37.30, -121.90], [37.33, -121.92]]
    maneuvers = [{"street_names": ["Airport Blvd"], "length": 4.0}]
    with respx.mock:
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(
                200, json=_trip(points, 4.0, maneuvers)))
        async with httpx.AsyncClient() as client:
            got = await roadsnap._snap_toll(
                client, 37.30, -121.90, 37.33, -121.92, 330.0, "101")
    assert got is None


async def test_snap_toll_widens_then_transient():
    """Both search radii coming back with no edge candidate is a
    transient miss (retryable), not a tombstone."""
    with respx.mock:
        route = respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(400, json={"error": "no edges"}))
        async with httpx.AsyncClient() as client:
            with pytest.raises(roadsnap.TransientSnapError):
                await roadsnap._snap_toll(
                    client, 37.30, -121.90, 37.33, -121.92, 330.0, "101")
    assert route.call_count == 2  # 60 m then 150 m


def test_apply_attaches_cached_and_queues_unknown():
    key = roadsnap._key(37.3, -121.9, 37.33, -121.92)
    roadsnap._mem[key] = json.dumps([[37.3, -121.9], [37.31, -121.905],
                                     [37.33, -121.92]])
    known = {"kind": "lane_closure", "lat": 37.3, "lon": -121.9,
             "end": [37.33, -121.92]}
    unknown = {"kind": "lane_closure", "lat": 38.0, "lon": -120.0,
               "end": [38.1, -120.1]}
    native = {"kind": "lane_closure", "lat": 39.0, "lon": -119.0,
              "path": [[39.0, -119.0], [39.01, -119.01], [39.02, -119.0]]}
    two_pt = {"kind": "lane_closure", "lat": 40.0, "lon": -118.0,
              "path": [[40.0, -118.0], [40.2, -118.3]]}
    roadsnap.apply([known, unknown, native, two_pt])
    assert len(known["path"]) == 3            # cached snap attached
    assert "path" not in unknown              # queued, dot for now
    assert len(roadsnap._queue) == 2          # unknown + the 2pt pair
    assert native["path"][1] == [39.01, -119.01]   # untouched


def test_failed_snaps_are_remembered_as_no_line():
    key = roadsnap._key(37.3, -121.9, 37.33, -121.92)
    roadsnap._mem[key] = None
    m = {"kind": "lane_closure", "lat": 37.3, "lon": -121.9,
         "end": [37.33, -121.92]}
    roadsnap.apply([m])
    assert "path" not in m and not roadsnap._queue


# --- boot mirror + worker gate -------------------------------------------

class _FakeSnap:
    def __init__(self, id_, doc):
        self.id = id_
        self._doc = doc

    def to_dict(self):
        return self._doc


class _FakeDb:
    """Just enough Firestore: one collection, a paged stream of docs
    (order_by / limit / start_after, the way the loader reads it), and
    a record of every document().set() the worker performs."""

    def __init__(self, docs=None, fail_stream=False):
        self.docs = docs or {}
        self.fail_stream = fail_stream
        self.sets: list[tuple[str, dict]] = []
        self.pages = 0
        self._limit = None
        self._after = None

    def collection(self, _name):
        return self

    def order_by(self, _field):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def start_after(self, snap):
        self._after = snap.id
        return self

    async def stream(self):
        self.pages += 1
        if self.fail_stream:
            raise RuntimeError("stream broke")
        ids = sorted(self.docs)
        if self._after is not None:
            ids = ids[ids.index(self._after) + 1:]
        if self._limit is not None:
            ids = ids[:self._limit]
        for k in ids:
            yield _FakeSnap(k, self.docs[k])

    def document(self, key):
        db = self

        class _Doc:
            async def set(self, data):
                db.sets.append((key, data))
        return _Doc()


async def test_load_persisted_mirrors_docs(monkeypatch, caplog):
    db = _FakeDb({
        "aaa": {"ok": True, "path": "[[37.3, -121.9], [37.33, -121.92]]"},
        "bbb": {"ok": False, "path": None},
    })
    monkeypatch.setattr(roadsnap, "_get_db", lambda: db)
    with caplog.at_level(logging.INFO, logger="roadsnap"):
        assert await roadsnap.load_persisted() is True
    assert roadsnap._loaded is True
    # Mirrored as the compact JSON string Firestore holds, decoded on
    # use: 19,600 paths as nested Python lists cost ~700 MB of RSS.
    assert roadsnap._mem["aaa"] == "[[37.3, -121.9], [37.33, -121.92]]"
    assert roadsnap._mem["bbb"] is None
    assert roadsnap.path_for(37.3, -121.9, 37.33, -121.92) is None  # unknown key
    roadsnap._mem[roadsnap._key(1, 2, 3, 4)] = "[[1, 2], [3, 4]]"
    assert roadsnap.path_for(1, 2, 3, 4) == [[1, 2], [3, 4]]
    assert "road_snaps loaded: 2 docs" in caplog.text


async def test_load_persisted_failure_is_not_loaded(monkeypatch, caplog):
    """A failed or partial mirror must not read as 'nothing is known':
    the worker would then re-buy every pair it sees."""
    monkeypatch.setattr(roadsnap, "_get_db", lambda: _FakeDb(fail_stream=True))
    with caplog.at_level(logging.ERROR, logger="roadsnap"):
        assert await roadsnap.load_persisted() is False
    assert roadsnap._loaded is False
    assert not roadsnap._mem
    assert "road_snaps load failed" in caplog.text


async def test_drain_never_buys_before_load_succeeds(monkeypatch):
    monkeypatch.setattr(roadsnap, "_get_db", lambda: _FakeDb(fail_stream=True))
    waits: list[float] = []

    async def fake_sleep(seconds):
        waits.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(roadsnap, "_sleep", fake_sleep)
    assert roadsnap.path_for(37.3, -121.9, 37.33, -121.92) is None
    with respx.mock:
        route = respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(200, json=_trip([[37.3, -121.9],
                                                         [37.33, -121.92]], 4.0)))
        async with httpx.AsyncClient() as client:
            with pytest.raises(asyncio.CancelledError):
                await roadsnap._drain(client)
    assert route.call_count == 0
    assert waits == [roadsnap.LOAD_RETRY_SECONDS]
    assert roadsnap._queue  # the pair is still waiting, not lost


async def test_drain_logs_and_persists_each_purchase(monkeypatch, caplog):
    db = _FakeDb()
    monkeypatch.setattr(roadsnap, "_get_db", lambda: db)

    async def fake_sleep(seconds):
        if seconds == roadsnap.PACE_SECONDS:
            raise asyncio.CancelledError  # one purchase, then stop

    monkeypatch.setattr(roadsnap, "_sleep", fake_sleep)
    key = roadsnap._key(37.3, -121.9, 37.33, -121.92)
    assert roadsnap.path_for(37.3, -121.9, 37.33, -121.92) is None
    points = [[37.3, -121.9], [37.31, -121.91], [37.33, -121.92]]
    with respx.mock, caplog.at_level(logging.INFO, logger="roadsnap"):
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(200, json=_trip(points, 4.0)))
        async with httpx.AsyncClient() as client:
            with pytest.raises(asyncio.CancelledError):
                await roadsnap._drain(client)
    assert json.loads(roadsnap._mem[key])[0] == [37.3, -121.9]
    assert roadsnap._mem[key] == db.sets[0][1]["path"]  # one string, both places
    assert db.sets and db.sets[0][0] == key and db.sets[0][1]["ok"] is True
    assert db.sets[0][1]["expire_at"] > datetime.now(UTC) + timedelta(days=300)
    assert f"snap closure {key} ok=True queue=0" in caplog.text


async def test_drain_warns_when_persist_fails(monkeypatch, caplog):
    """A purchase that never reaches Firestore is bought again after
    the next restart; that must be visible, not silent."""
    db = _FakeDb()

    class _Broken:
        async def set(self, _data):
            raise RuntimeError("firestore down")

    db.document = lambda _key: _Broken()
    monkeypatch.setattr(roadsnap, "_get_db", lambda: db)

    async def fake_sleep(seconds):
        if seconds == roadsnap.PACE_SECONDS:
            raise asyncio.CancelledError

    monkeypatch.setattr(roadsnap, "_sleep", fake_sleep)
    roadsnap.path_for(37.3, -121.9, 37.33, -121.92)
    with respx.mock, caplog.at_level(logging.WARNING, logger="roadsnap"):
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(200, json=_trip(
                [[37.3, -121.9], [37.33, -121.92]], 4.0)))
        async with httpx.AsyncClient() as client:
            with pytest.raises(asyncio.CancelledError):
                await roadsnap._drain(client)
    assert "snap persist failed" in caplog.text


async def test_drain_logs_router_errors_and_requeues(monkeypatch, caplog):
    db = _FakeDb()
    monkeypatch.setattr(roadsnap, "_get_db", lambda: db)
    waits: list[float] = []

    async def fake_sleep(seconds):
        waits.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(roadsnap, "_sleep", fake_sleep)
    key = roadsnap._key(37.3, -121.9, 37.33, -121.92)
    roadsnap.path_for(37.3, -121.9, 37.33, -121.92)
    with respx.mock, caplog.at_level(logging.WARNING, logger="roadsnap"):
        respx.post(url__regex=ROUTE_RE).mock(
            return_value=httpx.Response(503))
        async with httpx.AsyncClient() as client:
            with pytest.raises(asyncio.CancelledError):
                await roadsnap._drain(client)
    assert waits == [30]
    assert key in roadsnap._queue and key not in roadsnap._mem
    assert "snap retry later" in caplog.text and "HTTPStatusError" in caplog.text


async def test_load_persisted_reads_in_pages(monkeypatch):
    """A single query over the whole collection times out server-side
    on a busy boot (seen in production: 503 after 10,401 of 19,624
    docs). Pages keep every query short."""
    docs = {f"k{i:02d}": {"ok": True, "path": "[[1, 2], [3, 4]]"}
            for i in range(5)}
    db = _FakeDb(docs)
    monkeypatch.setattr(roadsnap, "_get_db", lambda: db)
    monkeypatch.setattr(roadsnap, "LOAD_PAGE", 2)
    assert await roadsnap.load_persisted() is True
    assert len(roadsnap._mem) == 5
    assert db.pages == 3  # 2 + 2 + 1


def test_toll_pair_for_decodes_cached_dict():
    a, b, brg, token = (37.30, -121.90), (37.33, -121.92), 330.0, "101"
    assert roadsnap.toll_pair_for(a, b, brg, token) is None  # queued
    key = roadsnap._queue[-1]
    roadsnap._mem[key] = json.dumps({"path": [[1, 2], [3, 4]], "a": [1, 2], "b": [3, 4]})
    got = roadsnap.toll_pair_for(a, b, brg, token)
    assert got == {"path": [[1, 2], [3, 4]], "a": [1, 2], "b": [3, 4]}
    roadsnap._mem[key] = None  # a rejected pair stays "no line"
    assert roadsnap.toll_pair_for(a, b, brg, token) is None
