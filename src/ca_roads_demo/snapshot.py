"""Snapshot publishing: the map's read path, moved off the request path.

Every visitor's boot used to ride through the single Cloud Run instance,
which had to have warm feed caches, assemble JSON and gzip it. A cold
edge entry cost seconds. Nothing about that work is per-user: the payload
is identical for everyone.

So a background loop builds it once per cycle and uploads pre-gzipped
objects to GCS, which sits behind Cloudflare. The browser fetches a
static object from the edge; no user request touches compute. Feed
warming and outages can no longer delay anyone, because the last good
snapshot is already on the edge.

Three bundles on their own cadences, because their data moves at very
different speeds and one hot object should not carry 3,300 cameras:

    live.json.gz     ~30 s   incidents, closures, chain controls, fires, tolls
    signs.json.gz    ~5 min  message signs and roadside weather
    cameras.json.gz  ~1 h    camera inventory

Roadside weather rides with signs rather than cameras: it changes every
few minutes, so an hourly object would publish it stale and the 30 s
object does not need the extra bulk.

/api/mapdata is untouched and still serves the assistant, routing, watch
areas and `fields=geo` lazy geometry. Only the map boot moved.
"""
from __future__ import annotations

import asyncio
import contextlib
import gzip
import hashlib
import json
import logging
import os
import time
from datetime import UTC, datetime

log = logging.getLogger("ca_roads_demo.snapshot")

# Bumped whenever the payload shape changes in a way an older page
# cannot read. Long-lived tabs (wall monitors) compare this against the
# value they booted with and reload themselves rather than break.
SCHEMA = 1

# Coverage-wide: one object serves every viewport, so every visitor
# shares one edge cache entry. The client already filters to the view.
WORLD_BOX = (-85.0, -180.0, 85.0, 180.0)

BUCKET = os.environ.get("SNAPSHOT_BUCKET", "")

# (object name, kinds, seconds between builds, Cache-Control, max_stale)
#
# max-age is short and stale-while-revalidate is long on purpose: the
# edge answers instantly from cache and revalidates behind the request,
# so nobody ever waits on an origin fetch. ETags make the client's 30 s
# poll a 304 costing a few bytes.
#
# max_stale is how long an object may go without being re-uploaded when
# the data has not changed. Only live.json.gz needs a tight one: it is
# the newest timestamp the client holds, so it alone drives the "data as
# of" chip, and letting it sit still for minutes during a quiet night
# would make a perfectly healthy display look stale.
BUNDLES: tuple[tuple[str, set[str], int, str, int], ...] = (
    ("live.json.gz", {"incident", "closure", "chain", "fire", "toll"}, 30,
     "public, max-age=15, stale-while-revalidate=180", 60),
    ("signs.json.gz", {"sign", "rwis"}, 300,
     "public, max-age=120, stale-while-revalidate=3600", 1800),
    ("cameras.json.gz", {"camera"}, 3600,
     "public, max-age=3600, stale-while-revalidate=86400", 21600),
)

# Hash of the MARKERS last uploaded, per object, and when that upload
# happened. The hash deliberately excludes the payload's `published`
# timestamp: hashing the whole body would change the digest every cycle,
# rotate the GCS ETag, and turn every client's cheap 304 poll into a
# full download of the object. Skipping an unchanged upload is what
# keeps an idle open map costing a few bytes per poll.
_last_hash: dict[str, str] = {}
_last_upload: dict[str, float] = {}
_last_published: dict[str, str] = {}


def _client():
    from google.cloud import storage
    return storage.Client()


def build_payload(markers, *, degraded: bool = False) -> dict:
    """The published object body.

    `published` is what the client's "data as of" chip reads, and it is
    the only honest signal during an outage: when the publisher stops,
    the timestamp ages visibly instead of the map silently freezing.
    """
    return {
        "schema": SCHEMA,
        "build": os.environ.get("APP_VERSION", ""),
        "published": datetime.now(UTC).isoformat(timespec="seconds"),
        "degraded": degraded,
        "markers": markers,
    }


def _encode(payload: dict) -> bytes:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return gzip.compress(raw, 6)


def _digest(markers) -> str:
    """Content hash of the markers alone (see _last_hash)."""
    return hashlib.md5(
        json.dumps(markers, separators=(",", ":")).encode()).hexdigest()


async def build_bundle(name: str, kinds: set[str]) -> list | None:
    """Build one bundle, or None when it must not be published.

    Skip-on-degraded (decision D2): a warming or degraded build ships a
    nearly-empty map to every visitor at once. Keeping the previous
    object means users always see a complete map, and the ageing
    timestamp is what tells them it is old. This is the same call the
    request path already makes for its own cache, moved to where it
    belongs.
    """
    from ca_roads_demo import app as demo_app

    markers, ready, total, degraded = await demo_app.build_markers(
        WORLD_BOX, kinds)
    if ready < total:
        log.info("snapshot %s: skipped, feeds warming (%s/%s)",
                 name, ready, total)
        return None
    if degraded:
        log.warning("snapshot %s: skipped, degraded build (%d markers)",
                    name, len(markers))
        return None
    return demo_app.shape_markers(markers, slim=True)


def _upload(name: str, body: bytes, cache_control: str) -> None:
    """Blocking GCS write; callers run it off the event loop.

    content_encoding='gzip' with content_type='application/json' is what
    makes this a pre-compressed object: GCS serves the bytes as-is with
    Content-Encoding: gzip and the browser inflates them. Compressing
    once per cycle instead of once per request is the whole point.
    """
    blob = _client().bucket(BUCKET).blob(name)
    blob.cache_control = cache_control
    blob.content_encoding = "gzip"
    blob.upload_from_string(body, content_type="application/json")


async def publish_once(name: str, kinds: set[str], cache_control: str,
                       max_stale: int = 0) -> bool:
    """Build and upload one bundle. True when bytes actually shipped."""
    markers = await build_bundle(name, kinds)
    if markers is None:
        return False
    digest = _digest(markers)
    aged = time.time() - _last_upload.get(name, 0.0)
    if _last_hash.get(name) == digest and aged < max_stale:
        return False              # unchanged: keep the ETag stable
    body = _encode(build_payload(markers))
    await asyncio.to_thread(_upload, name, body, cache_control)
    _last_hash[name] = digest
    _last_upload[name] = time.time()
    _last_published[name] = datetime.now(UTC).isoformat(timespec="seconds")
    log.info("snapshot %s: published %d markers, %d bytes gzipped",
             name, len(markers), len(body))
    return True


async def _bundle_loop(name: str, kinds: set[str], interval: int,
                       cache_control: str, max_stale: int) -> None:
    while True:
        with contextlib.suppress(Exception):
            await publish_once(name, kinds, cache_control, max_stale)
        await asyncio.sleep(interval)


async def run() -> None:
    """Publish every bundle on its own cadence, forever.

    Started from the app lifespan. Without SNAPSHOT_BUCKET set this is a
    no-op, so local development and tests never touch GCS and the site
    keeps serving from /api/mapdata exactly as before.
    """
    if not BUCKET:
        log.info("snapshot publisher disabled (no SNAPSHOT_BUCKET)")
        return
    # Let the boot prewarm land first: publishing before the feeds are
    # warm just burns a cycle that build_bundle would skip anyway.
    await asyncio.sleep(5)
    await asyncio.gather(*(
        _bundle_loop(name, kinds, interval, cc, stale)
        for name, kinds, interval, cc, stale in BUNDLES
    ))


def status() -> dict:
    """Publisher health, surfaced on /api/warmup for ops."""
    return {
        "bucket": BUCKET or None,
        "schema": SCHEMA,
        "objects": {name: {"published": _last_published.get(name),
                           "hash": _last_hash.get(name, "")[:8] or None}
                    for name, *_rest in BUNDLES},
        "checked_at": time.time(),
    }
