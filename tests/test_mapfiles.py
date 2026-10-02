"""The base map as our own files: the styles, the manifest, and the
corridor cut along a route."""

import asyncio
import json
import sys

import pytest
from starlette.testclient import TestClient

from ca_roads_demo import mapfiles

OURS = ("slate", "grayscale", "dark", "light")       # themes over our own map file
OPENFREEMAP = ("positron", "bright")                 # OpenFreeMap's styles, as published


def test_every_style_is_complete_and_points_at_its_tiles():
    assert set(mapfiles.FLAVORS) == set(OURS + OPENFREEMAP)
    for flavor in mapfiles.FLAVORS:
        spec = mapfiles.style_json(flavor)
        assert spec["version"] == 8 and spec["layers"], flavor
        # Driving map: no points of interest.
        assert not [layer["id"] for layer in spec["layers"] if layer["id"].startswith("poi")]
        assert "__" not in json.dumps(spec)
    for flavor in OURS:
        spec = mapfiles.style_json(flavor)
        assert spec["sources"]["protomaps"]["url"] == "pmtiles://https://data.commutescout.com/map/us.pmtiles"
        assert spec["glyphs"].startswith("https://data.commutescout.com/map/assets/fonts/")
        assert spec["sprite"].startswith("https://data.commutescout.com/map/assets/sprites/v4/")
    for flavor in OPENFREEMAP:
        spec = mapfiles.style_json(flavor)
        assert spec["sources"]["openmaptiles"]["url"] == "https://tiles.openfreemap.org/planet"
        assert spec["glyphs"].startswith("https://tiles.openfreemap.org/fonts/")


def test_every_style_has_a_picture_for_the_picker():
    thumbs = mapfiles.STYLE_DIR / "thumbs"
    for flavor in ("positron", "bright", "slate", "grayscale", "dark"):
        assert (thumbs / f"{flavor}.webp").stat().st_size > 1000, flavor


def test_a_phone_fills_the_placeholders_with_its_own_paths():
    spec = mapfiles.style_json("dark", pmtiles_url="file:///data/corridor.pmtiles",
                               assets_url="asset://map")
    assert spec["sources"]["protomaps"]["url"] == "pmtiles://file:///data/corridor.pmtiles"
    assert spec["glyphs"] == "asset://map/fonts/{fontstack}/{range}.pbf"


def test_the_region_follows_the_route_and_stops_at_its_ends():
    path = [(37.0, -122.0), (37.0, -121.9), (37.1, -121.9)]   # about 9 km then 11 km
    pts = mapfiles.sample(path, every_m=2000)
    assert pts[0] == path[0] and pts[-1] == path[-1]
    assert 9 <= len(pts) <= 13
    region = mapfiles.corridor_region(path, buffer_m=2500)
    assert region["geometry"]["type"] == "MultiPolygon"
    assert len(region["geometry"]["coordinates"]) == len(pts)
    square = region["geometry"]["coordinates"][0][0]
    assert square[0] == square[-1] and len(square) == 5
    # Each square is about five kilometres across.
    assert 0.040 < square[2][1] - square[0][1] < 0.050


def test_a_path_is_checked_before_anything_runs():
    with pytest.raises(ValueError):
        mapfiles.parse_path({"path": [[37, -122]]})
    with pytest.raises(ValueError):
        mapfiles.parse_path({"path": [[91, 0], [0, 0]]})
    with pytest.raises(ValueError):
        mapfiles.parse_path({"path": "nope"})
    parsed = mapfiles.parse_path({"path": [["37.1", "-122.2"], [37.2, -122.3]]})
    assert parsed == [(37.1, -122.2), (37.2, -122.3)]


@pytest.fixture
def fake_pmtiles(tmp_path, monkeypatch):
    """A stand-in for the Go tool: writes the region it was given into
    the output file, so the test can see what the cut asked for."""
    script = tmp_path / "pmtiles.py"
    script.write_text(
        "import sys, shutil\n"
        "args = sys.argv[1:]\n"
        "assert args[0] == 'extract', args\n"
        "region = [a for a in args if a.startswith('--region=')][0][len('--region='):]\n"
        "shutil.copy(region, args[2])\n", encoding="utf-8")
    runner = tmp_path / ("pmtiles.cmd" if sys.platform == "win32" else "pmtiles")
    if sys.platform == "win32":
        runner.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8")
    else:
        runner.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        runner.chmod(0o755)
    monkeypatch.setattr(mapfiles, "PMTILES_BIN", str(runner))
    return runner


def test_the_cut_runs_the_tool_on_the_corridor(fake_pmtiles):
    region = mapfiles.corridor_region([(37.0, -122.0), (37.0, -121.95)])
    out = asyncio.run(mapfiles.extract(region, source="https://example.test/us.pmtiles"))
    try:
        assert json.loads(out.read_text(encoding="utf-8")) == region
    finally:
        import shutil
        shutil.rmtree(out.parent, ignore_errors=True)


def test_the_extract_endpoint_answers_with_the_file_and_refuses_long_routes(fake_pmtiles):
    from ca_roads_demo.app import app

    with TestClient(app) as c:
        r = c.post("/api/map/extract", json={"path": [[37.0, -122.0], [37.0, -121.95]]})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/vnd.pmtiles")
        assert json.loads(r.content)["geometry"]["type"] == "MultiPolygon"
        assert r.headers["X-Map-Route-Km"] == "4"
        far = c.post("/api/map/extract", json={"path": [[25.0, -80.0], [47.0, -122.0]]})
        assert far.status_code == 400 and "states" in far.json()["error"]
        bad = c.post("/api/map/extract", json={"path": "x"})
        assert bad.status_code == 400


def test_the_style_endpoint_serves_each_flavor():
    from ca_roads_demo.app import app

    with TestClient(app) as c:
        r = c.get("/api/map/style.json?flavor=grayscale")
        assert r.status_code == 200 and r.json()["name"] == "commutescout-grayscale"
        assert c.get("/api/map/style.json?flavor=sepia").status_code == 400
