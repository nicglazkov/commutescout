"""/api/hero-dots: every live road event as a bare point, for the home
page's national map.

/api/mapdata answers the same question with everything a popup needs,
which for the whole country is about 7 MB. The home page only draws a
dot per event, so this ships position and kind and nothing else:
coordinates rounded to two decimals (about a kilometre, far finer than
a 975-pixel-wide map can show), points that round to the same spot
collapsed into one, and the lot gzipped. That is a few tens of
kilobytes for the whole country.

The markers come from build_markers, the same code the map and the
snapshot publisher use, so the dots are the map's dots. The built body
is kept for 30 s, matching the map's refresh and the Cache-Control
header, so a busy home page costs one build per half minute.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.responses import Response

# The map's kind names, shortened to one letter for the wire.
KINDS = {"incident": "i", "lane_closure": "c", "chain_control": "h",
         "wildfire": "f"}
WANT = {"incident", "closure", "chain", "fire"}
WORLD_BOX = (-85.0, -180.0, 85.0, 180.0)
TTL_S = 30

# (built_at monotonic, etag, gzipped body)
_cache: tuple[float, str, bytes] | None = None


def compact(markers, at: str) -> dict:
    """Group markers by kind as flat [lat, lon, lat, lon, ...] lists,
    rounded to two decimals, with repeats at one rounded spot dropped."""
    out: dict[str, list[float]] = {k: [] for k in KINDS.values()}
    seen: set[tuple[str, float, float]] = set()
    for m in markers:
        k = KINDS.get(m.get("kind"))
        lat, lon = m.get("lat"), m.get("lon")
        if k is None or not isinstance(lat, int | float) \
                or not isinstance(lon, int | float):
            continue
        key = (k, round(lat, 2), round(lon, 2))
        if key in seen:
            continue
        seen.add(key)
        out[k].extend(key[1:])
    return {"at": at, **out}


def clear_cache() -> None:
    global _cache
    _cache = None


async def api_hero_dots(request: Request):
    global _cache
    # Looked up at call time: app.py imports this module, and tests
    # replace build_markers on the app module.
    from ca_roads_demo import app as demo_app

    now = time.monotonic()
    if _cache and now - _cache[0] < TTL_S:
        _ts, etag, gz_body = _cache
        warming = False
    else:
        markers, ready, total, _degraded = await demo_app.build_markers(
            WORLD_BOX, WANT)
        warming = ready < total
        at = datetime.now(UTC).replace(microsecond=0).isoformat()

        def _build():
            raw = json.dumps(compact(markers, at),
                             separators=(",", ":")).encode()
            return raw, gzip.compress(raw, 6)

        raw_body, gz_body = await asyncio.to_thread(_build)
        etag = f'"{hashlib.md5(raw_body).hexdigest()}"'
        # A fresh instance still filling its feed caches would publish a
        # thin map for 30 s; serve it, but build again on the next call.
        if not warming:
            _cache = (now, etag, gz_body)

    headers = {
        "ETag": etag,
        "Cache-Control": ("no-store" if warming
                          else "public, max-age=30, "
                               "stale-while-revalidate=60"),
        "Vary": "Accept-Encoding",
    }
    if etag in (request.headers.get("if-none-match") or ""):
        return Response(status_code=304, headers=headers)
    if "gzip" in (request.headers.get("accept-encoding") or ""):
        return Response(gz_body, media_type="application/json",
                        headers={**headers, "Content-Encoding": "gzip"})
    return Response(gzip.decompress(gz_body), media_type="application/json",
                    headers=headers)
