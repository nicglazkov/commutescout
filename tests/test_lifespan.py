"""App lifespan: the snap mirror loads during container startup.

Cloud Run allocates CPU to a request-billed instance only during
startup and while a request is in flight. The demo takes about two
requests a minute (health checks), so a background load of the mirror
crawls at a few documents a second and hits Firestore's server-side
deadline. Startup is the one window with full CPU, and uvicorn opens
the port only after lifespan startup returns."""

import asyncio

from ca_roads_demo import app, roadsnap, snapshot, vitals


async def _noop():
    return None


def _quiet_background(monkeypatch):
    monkeypatch.setattr(app, "_prewarm", _noop)
    monkeypatch.setattr(snapshot, "run", _noop)
    monkeypatch.setattr(vitals, "run", _noop)


async def test_lifespan_loads_snap_mirror_before_serving(monkeypatch):
    _quiet_background(monkeypatch)
    calls: list[str] = []

    async def fake_load():
        calls.append("load")
        return True

    monkeypatch.setattr(roadsnap, "load_persisted", fake_load)
    async with app._lifespan(None):
        assert calls == ["load"]


async def test_lifespan_gives_up_on_a_slow_load_and_still_serves(monkeypatch):
    """A load that outlives the startup budget must not hold the port
    closed past the startup probe; the worker retries it later."""
    _quiet_background(monkeypatch)

    async def slow_load():
        await asyncio.sleep(30)
        return True

    monkeypatch.setattr(roadsnap, "load_persisted", slow_load)
    monkeypatch.setattr(app, "SNAP_LOAD_STARTUP_SECONDS", 0.05)
    async with app._lifespan(None):
        pass  # reached: the timeout was swallowed


async def test_lifespan_survives_a_failed_load(monkeypatch):
    _quiet_background(monkeypatch)

    async def broken_load():
        raise RuntimeError("no firestore here")

    monkeypatch.setattr(roadsnap, "load_persisted", broken_load)
    async with app._lifespan(None):
        pass
