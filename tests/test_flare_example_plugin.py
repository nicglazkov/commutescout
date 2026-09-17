"""The example plugin passes the conformance check and behaves as the
specification says, so it is a safe template for plugin authors."""

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from ca_roads import flare

SERVER = Path(__file__).resolve().parent.parent / "examples" / "flare-plugin" / "server.py"


def load_plugin():
    spec = importlib.util.spec_from_file_location("flare_example_server", SERVER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flare_example_server"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_example_plugin_passes_the_conformance_check():
    mod = load_plugin()
    transport = httpx.ASGITransport(app=mod.app)
    async with httpx.AsyncClient(transport=transport, base_url="https://plugin.example") as c:
        rep = await flare.check_plugin("https://plugin.example", client=c)
    assert rep.success, rep.text()
    assert "confirm round trip" in rep.passed


@pytest.mark.asyncio
async def test_example_plugin_rules():
    mod = load_plugin()
    transport = httpx.ASGITransport(app=mod.app)
    async with httpx.AsyncClient(transport=transport, base_url="https://plugin.example") as c:
        hs = (await c.get("/flare/v1/handshake")).json()
        assert flare.validate_handshake(hs) == []
        r = await c.get("/flare/v1/alerts", params={"lat": 60, "lon": -100, "r": 1000})
        assert r.status_code == 422 and r.json()["error"]["code"] == "outside_coverage"
        r = await c.post("/flare/v1/report", json={"kind": "UFO", "lat": 37, "lon": -122})
        assert r.status_code == 422
        r = await c.post("/flare/v1/report", json={"kind": "CRASH_MAJOR", "lat": 37.5,
                                                   "lon": -122.2, "reporter": "r:a"})
        assert r.status_code == 201
        alert = r.json()["alert"]
        assert flare.validate_alert(alert) == [] and alert["notify"] is True
        near = (await c.get("/flare/v1/alerts",
                            params={"lat": 37.5, "lon": -122.2, "r": 500})).json()
        assert [a["id"] for a in near["alerts"]] == [alert["id"]]
        # The reporter's own vote does not count; another reporter's does.
        same = await c.post("/flare/v1/confirm", json={"alert_id": alert["id"], "vote": "up",
                                                       "reporter": "r:a"})
        assert same.json()["n_confirmations"] == 0
        other = await c.post("/flare/v1/confirm", json={"alert_id": alert["id"], "vote": "up",
                                                        "reporter": "r:b"})
        assert other.json()["n_confirmations"] == 1
        missing = await c.post("/flare/v1/confirm", json={"alert_id": "x", "vote": "up"})
        assert missing.status_code == 404
