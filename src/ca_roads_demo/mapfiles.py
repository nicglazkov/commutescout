"""The base map as files of our own, and the pieces cut from it.

The apps draw the map from a vector tile archive (PMTiles) cut from the
Protomaps world build: the United States at full detail, one file on
the data host, read by byte range. Three styles, generated from the
Protomaps basemap styles and trimmed for driving, are bundled in the
apps so the map draws with no signal; the same styles are served here
for the website and for anyone building against the data.

Offline, a phone needs a piece of the map on disk. Two kinds:

- a route corridor, cut here on request (``POST /api/map/extract``)
  from the big file, a few kilometres either side of the route, tens
  of megabytes, fetched by the app when a trip starts;
- a whole state, cut ahead of time by the refresh job and listed in
  the manifest with its size, chosen by the driver in Settings.

The cut runs the ``pmtiles`` tool (Go, in the image) against the big
file over HTTP range reads, so only the tiles inside the region are
ever moved. ``MAP_BASE_URL`` points at the folder on the data host.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import shutil
import tempfile
import time
from pathlib import Path

import httpx
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

log = logging.getLogger(__name__)

# The map files live on Cloudflare R2 behind maps.commutescout.com since
# 2026-10-03 (zero egress cost); the GCS copy under data.commutescout.com/map
# is kept for a while as a fallback.
MAP_BASE_URL = os.environ.get("MAP_BASE_URL", "https://maps.commutescout.com").rstrip("/")
PMTILES_BIN = os.environ.get("PMTILES_BIN", "pmtiles")
STYLE_DIR = Path(__file__).parent / "static" / "mapstyle"
# positron and bright are OpenFreeMap's styles (OpenMapTiles layout);
# the rest are themes over our own map file (Protomaps layout).
FLAVORS = ("positron", "bright", "slate", "grayscale", "dark", "light")

# A corridor: this far either side of the route, at this detail.
BUFFER_M = 2_500
MAX_BUFFER_M = 6_000
MAX_ZOOM = 15
# The route is sampled every SAMPLE_M for the region; past MAX_ROUTE_M
# the corridor would be larger than a state file and is refused.
SAMPLE_M = 2_000
MAX_ROUTE_M = 800_000
MAX_POINTS = 2_000
# One cut takes seconds to a minute of upstream reads; a few at once is
# plenty for one instance, and a slow one cannot run forever.
CONCURRENT_EXTRACTS = 2
EXTRACT_TIMEOUT_S = 240
MANIFEST_TTL_S = 600

_extracts = asyncio.Semaphore(CONCURRENT_EXTRACTS)
_manifest_cache: tuple[float, dict] | None = None


def style_json(flavor: str, *, pmtiles_url: str | None = None,
               assets_url: str | None = None) -> dict:
    """One of the bundled styles with its placeholders filled in."""
    if flavor not in FLAVORS:
        raise KeyError(flavor)
    text = (STYLE_DIR / f"{flavor}.json").read_text(encoding="utf-8")
    text = text.replace("__PMTILES_URL__", pmtiles_url or f"{MAP_BASE_URL}/us.pmtiles")
    text = text.replace("__ASSETS__", assets_url or f"{MAP_BASE_URL}/assets")
    return json.loads(text)


# OpenFreeMap's styles name their tiles by a second document (a TileJSON)
# that says where this week's tiles are. Read by the browser that is one
# more round trip before the first tile; read here, every so often, it
# rides inside the style and the map starts on the tiles at once.
TILEJSON_TTL_S = 1800
_tilejson_cache: dict[str, tuple[float, dict]] = {}


async def _inline_tilejson(spec: dict, client: httpx.AsyncClient) -> dict:
    """Replace a vector source's TileJSON address with what it says.
    Any failure leaves the address in place, which still works."""
    for source in spec.get("sources", {}).values():
        url = source.get("url")
        if source.get("type") != "vector" or not isinstance(url, str) or not url.startswith("https://"):
            continue
        hit = _tilejson_cache.get(url)
        if not hit or time.monotonic() - hit[0] > TILEJSON_TTL_S:
            try:
                r = await client.get(url, timeout=5.0)
                r.raise_for_status()
                doc = r.json()
                if not doc.get("tiles"):
                    raise ValueError("no tiles")
                hit = (time.monotonic(), doc)
                _tilejson_cache[url] = hit
            except Exception as exc:  # noqa: BLE001
                log.warning("tilejson %s: %s", url, exc)
                if not hit:
                    continue
        doc = hit[1]
        del source["url"]
        for key in ("tiles", "minzoom", "maxzoom", "bounds", "attribution"):
            if key in doc:
                source[key] = doc[key]
    return spec


async def api_style(request: Request) -> Response:
    flavor = request.query_params.get("flavor") or "light"
    try:
        spec = style_json(flavor)
    except KeyError:
        return JSONResponse({"error": "flavor must be one of " + ", ".join(FLAVORS)},
                            status_code=400)
    from ca_roads_demo import app as demo

    spec = await _inline_tilejson(spec, demo.tools.get_road().client)
    return JSONResponse(spec, headers={"Cache-Control": "public, max-age=3600",
                                       "Access-Control-Allow-Origin": "*"})


async def _fetch_index(client: httpx.AsyncClient) -> dict:
    """The index the refresh job writes beside the files: which build,
    the US file's size, and every state file with its size."""
    global _manifest_cache
    now = time.monotonic()
    if _manifest_cache and now - _manifest_cache[0] < MANIFEST_TTL_S:
        return _manifest_cache[1]
    r = await client.get(f"{MAP_BASE_URL}/index.json", timeout=10.0)
    r.raise_for_status()
    index = r.json()
    _manifest_cache = (now, index)
    return index


async def api_manifest(request: Request) -> Response:
    """What the apps need to know: where the US file is, how big, which
    build, the states on offer, and the style URLs."""
    from ca_roads_demo import app as demo

    try:
        index = await _fetch_index(demo.tools.get_road().client)
    except Exception as exc:  # noqa: BLE001 - the index is a static file; say so
        log.warning("map index unavailable: %s", exc)
        return JSONResponse({"error": "map index unavailable"}, status_code=503)
    out = {
        "build": index.get("build"),
        "us": {"url": f"{MAP_BASE_URL}/us.pmtiles", "bytes": index.get("us_bytes")},
        "assets": f"{MAP_BASE_URL}/assets",
        "styles": {f: f"/api/map/style.json?flavor={f}" for f in FLAVORS},
        "states": [{"code": s["code"], "name": s["name"], "bytes": s["bytes"],
                    "url": f"{MAP_BASE_URL}/states/{s['code']}.pmtiles"}
                   for s in index.get("states", [])],
        "corridor": {"buffer_m": BUFFER_M, "max_route_m": MAX_ROUTE_M},
    }
    return JSONResponse(out, headers={"Cache-Control": "public, max-age=600",
                                      "Access-Control-Allow-Origin": "*"})


# ------------------------------------------------------------- corridor


def _meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    dx = (b[1] - a[1]) * 111_320 * k
    dy = (b[0] - a[0]) * 110_540
    return math.hypot(dx, dy)


def sample(path: list[tuple[float, float]], every_m: float = SAMPLE_M) -> list[tuple[float, float]]:
    """Points along the route about ``every_m`` apart, ends included."""
    if len(path) < 2:
        return list(path)
    out = [path[0]]
    since = 0.0
    for a, b in zip(path, path[1:], strict=False):
        d = _meters(a, b)
        if d == 0:
            continue
        pos = 0.0
        while since + (d - pos) >= every_m:
            step = every_m - since
            pos += step
            t = pos / d
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            since = 0.0
        since += d - pos
    if out[-1] != path[-1]:
        out.append(path[-1])
    return out


def corridor_region(path: list[tuple[float, float]], buffer_m: float = BUFFER_M) -> dict:
    """A GeoJSON MultiPolygon of squares along the route, each
    ``buffer_m`` from its centre: what the extract keeps. Squares
    overlap, which is fine, the tool takes the union of tiles."""
    polys = []
    for lat, lon in sample(path):
        d_lat = buffer_m / 110_540
        d_lon = buffer_m / max(1.0, 111_320 * math.cos(math.radians(lat)))
        polys.append([[[lon - d_lon, lat - d_lat], [lon + d_lon, lat - d_lat],
                       [lon + d_lon, lat + d_lat], [lon - d_lon, lat + d_lat],
                       [lon - d_lon, lat - d_lat]]])
    return {"type": "Feature", "properties": {},
            "geometry": {"type": "MultiPolygon", "coordinates": polys}}


def route_length_m(path: list[tuple[float, float]]) -> float:
    return sum(_meters(a, b) for a, b in zip(path, path[1:], strict=False))


def parse_path(body: dict) -> list[tuple[float, float]]:
    raw = body.get("path")
    if not isinstance(raw, list) or len(raw) < 2 or len(raw) > MAX_POINTS:
        raise ValueError(f"path must be 2 to {MAX_POINTS} [lat, lon] pairs")
    out = []
    for p in raw:
        try:
            lat, lon = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError("path entries are [lat, lon]") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("path entries are [lat, lon]")
        out.append((lat, lon))
    return out


async def extract(region: dict, *, source: str | None = None, maxzoom: int = MAX_ZOOM) -> Path:
    """Run the cut. Returns the file in a fresh temp folder the caller
    removes. Raises on a failed or overlong run."""
    src = source or f"{MAP_BASE_URL}/us.pmtiles"
    folder = Path(tempfile.mkdtemp(prefix="corridor-"))
    region_file = folder / "region.geojson"
    region_file.write_text(json.dumps(region), encoding="utf-8")
    out = folder / "corridor.pmtiles"
    proc = await asyncio.create_subprocess_exec(
        PMTILES_BIN, "extract", src, str(out), f"--region={region_file}", f"--maxzoom={maxzoom}",
        "--download-threads=4", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        output, _ = await asyncio.wait_for(proc.communicate(), timeout=EXTRACT_TIMEOUT_S)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        shutil.rmtree(folder, ignore_errors=True)
        raise RuntimeError("the cut took too long") from None
    if proc.returncode != 0 or not out.exists():
        shutil.rmtree(folder, ignore_errors=True)
        raise RuntimeError(f"pmtiles extract failed: {output.decode(errors='replace')[-300:]}")
    return out


async def api_extract(request: Request) -> Response:
    """Cut the map along a route and hand the file back.

    Body: ``{"path": [[lat, lon], ...], "buffer_m": 2500}``. The answer
    is the PMTiles file itself; the app keeps it and points the map at
    it when there is no signal.
    """
    from ca_roads_demo import app as demo

    body = await demo._capped_json(request)
    if body is None:
        return JSONResponse({"error": "body too large"}, status_code=413)
    try:
        path = parse_path(body)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    length = route_length_m(path)
    if length > MAX_ROUTE_M:
        return JSONResponse({"error": f"route is {length / 1000:.0f} km; corridors stop at "
                                      f"{MAX_ROUTE_M // 1000} km. Download the states instead."},
                            status_code=400)
    try:
        buffer_m = min(MAX_BUFFER_M, max(500.0, float(body.get("buffer_m") or BUFFER_M)))
    except (TypeError, ValueError):
        buffer_m = float(BUFFER_M)
    if demo._client_over_daily(request, "map-extract"):
        return JSONResponse({"error": "daily limit for map downloads reached"}, status_code=429,
                            headers={"Retry-After": "3600"})
    region = corridor_region(path, buffer_m)
    started = time.monotonic()
    async with _extracts:
        try:
            out = await extract(region)
        except RuntimeError as exc:
            log.warning("corridor extract failed: %s", exc)
            return JSONResponse({"error": "could not cut the map right now"}, status_code=502)
    size = out.stat().st_size
    log.info("corridor: %.0f km route, %d samples, %.1f MB in %.1f s", length / 1000,
             len(region["geometry"]["coordinates"]), size / 1e6, time.monotonic() - started)

    folder = out.parent

    async def cleanup():
        shutil.rmtree(folder, ignore_errors=True)

    from starlette.background import BackgroundTask
    return FileResponse(str(out), media_type="application/vnd.pmtiles",
                        filename="corridor.pmtiles",
                        headers={"X-Map-Route-Km": f"{length / 1000:.0f}",
                                 "Cache-Control": "no-store"},
                        background=BackgroundTask(cleanup))
