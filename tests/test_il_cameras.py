"""Illinois cameras survive a bad minute on the camera backend."""

import httpx
import pytest

from ca_roads_demo import states

INCIDENTS = "x,y,Description,Location,ClosureDetails\n-88.0,41.8,Crash,I-88 at York,\n"
CAMERAS = ("x,y,SnapShot,CameraLocation,CameraDirection,TooOld\n"
           "-87.9,41.9,https://cctv.example/a.jpg,I-290 at Harlem,E,false\n")


def _client(camera_status: int) -> httpx.AsyncClient:
    def handler(req):
        if req.url.path.endswith("incidentInfo.csv"):
            return httpx.Response(200, text=INCIDENTS)
        if camera_status != 200:
            return httpx.Response(camera_status)
        return httpx.Response(200, text=CAMERAS)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_a_failed_camera_file_keeps_the_last_cameras(monkeypatch):
    monkeypatch.setattr(states, "_IL_CAMERAS", None)
    async with _client(200) as c:
        first = await states._fetch_il(c)
    async with _client(502) as c:
        second = await states._fetch_il(c)
    kinds = [m["kind"] for m in second["markers"]]
    assert kinds.count("incident") == 1
    assert kinds.count("camera") == 1, "the last good camera list stands in"
    assert [m for m in first["markers"] if m["kind"] == "camera"] == \
        [m for m in second["markers"] if m["kind"] == "camera"]


@pytest.mark.asyncio
async def test_a_very_old_camera_list_is_not_served(monkeypatch):
    monkeypatch.setattr(states, "_IL_CAMERAS", (-1e9, [{"kind": "camera"}]))
    async with _client(502) as c:
        out = await states._fetch_il(c)
    assert [m["kind"] for m in out["markers"]] == ["incident"]
