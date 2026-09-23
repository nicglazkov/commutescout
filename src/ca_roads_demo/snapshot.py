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
    ("live.json.gz", {"incident", "closure", "chain", "fire", "toll", "plugin"}, 30,
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
# How many missed cycles make a bundle stuck rather than merely quiet.
STALE_CYCLES = 20
# A bundle that skipped (feeds still warming) tries again shortly rather
# than waiting out its whole interval. The camera bundle publishes
# hourly, so one skip after a deploy used to leave the last object up
# for another hour.
RETRY_AFTER_SKIP_S = 45
# A published object with a whole state missing looks healthy: it has
# thousands of markers and a fresh timestamp. Guard on the drop instead,
# and keep the previous object until the feed recovers.
DROP_FRACTION = 0.6
# Seconds the live bundle waits for a slow feed; see build_bundle.
LIVE_FEED_BUDGET_S = 15.0
_started = time.monotonic()
_last_hash: dict[str, str] = {}
_last_count: dict[str, int] = {}
_last_upload: dict[str, float] = {}
_last_published: dict[str, str] = {}

# Camera bundles carry a source forward instead of dropping it.
#
# A camera list is an inventory: where each camera is and the address of
# its image, which the viewer fetches live. When one source fails for a
# while, publishing without it makes thousands of cameras vanish for an
# hour at a time. The in-process fallbacks cover a feed that stumbles,
# but not one that is failing when the process starts, which is exactly
# when a deploy or a restart builds the next bundle. The previous bundle
# lives in the bucket and survives both, so a source it had and this
# build lacks is taken from there, for up to CARRY_MAX_S.
CARRY_BUNDLES = frozenset({"cameras.json.gz"})
CARRY_MIN = 50            # a source this small is not worth guarding
CARRY_FRACTION = 0.5      # below this share of its last count, carry it
CARRY_MAX_S = 6 * 3600.0
_previous: dict[str, list] = {}
_carried_since: dict[tuple[str, str], float] = {}


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


def _source_of(marker: dict) -> str:
    """Which source a marker came from: its declared source, else the
    host serving its image, which is one agency's camera system."""
    if marker.get("src"):
        return str(marker["src"])
    url = marker.get("image") or marker.get("stream") or ""
    host = url.split("://", 1)[-1].split("/", 1)[0]
    return host or marker.get("kind", "")


def _download_previous(name: str) -> list:
    """The markers of the object currently published, or none."""
    try:
        data = _client().bucket(BUCKET).blob(name).download_as_bytes()
        # The storage client may already have undone the gzip encoding.
        with contextlib.suppress(OSError):
            data = gzip.decompress(data)
        return json.loads(data).get("markers") or []
    except Exception as exc:  # noqa: BLE001 - no previous object is a normal start
        log.info("snapshot %s: no previous object to carry from (%s)",
                 name, type(exc).__name__)
        return []


async def carry_forward(name: str, markers: list) -> list:
    """This build's markers, with any source that went missing since the
    last publish taken from the last publish instead."""
    if name not in CARRY_BUNDLES:
        return markers
    if name not in _previous:
        _previous[name] = await asyncio.to_thread(_download_previous, name)
    before: dict[str, list] = {}
    for m in _previous[name]:
        before.setdefault(_source_of(m), []).append(m)
    now_counts: dict[str, int] = {}
    for m in markers:
        src = _source_of(m)
        now_counts[src] = now_counts.get(src, 0) + 1
    out = markers
    now = time.monotonic()
    for src, old in before.items():
        key = (name, src)
        if len(old) < CARRY_MIN or now_counts.get(src, 0) >= len(old) * CARRY_FRACTION:
            _carried_since.pop(key, None)
            continue
        since = _carried_since.setdefault(key, now)
        if now - since > CARRY_MAX_S:
            continue   # gone for good, or long enough to say so
        log.warning("snapshot %s: carrying %d markers from %s, which sent %d",
                    name, len(old), src, now_counts.get(src, 0))
        out = [m for m in out if _source_of(m) != src] + old
    return out


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
    from ca_roads_demo import states

    # A viewport request gives the other states' feeds a few seconds and
    # serves whatever answered, because a person is waiting. Nobody waits
    # on the publisher, and what it builds is served to every visitor
    # until the next build, so the slow bundles wait as long as any one
    # feed is allowed to take. With the short budget a feed that was
    # mid-refresh simply went missing: the camera bundle swung between
    # 9,652 and 22,262 cameras over one day for no reason but timing.
    # The live bundle is rebuilt every 30 seconds, and a feed that has
    # been dead a while is retried once a minute at up to a minute a
    # try, so it gets a middle budget rather than stalling behind one.
    budget = LIVE_FEED_BUDGET_S if name == "live.json.gz" else states.FETCH_CAP_SECONDS + 5
    markers, ready, total, degraded = await demo_app.build_markers(
        WORLD_BOX, kinds, feed_budget=budget)
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
    markers = await carry_forward(name, markers)
    # A feed that drops out takes its markers with it, and the bundle
    # would publish anyway: cameras.json.gz once shipped 14,791 cameras
    # with not one of them in California, because that one feed was
    # missing while every other state was fine. The count alone reads as
    # healthy, so compare it with what was last published.
    before = _last_count.get(name)
    if before and len(markers) < before * DROP_FRACTION:
        log.warning("snapshot %s: skipped, %d markers against %d last time; "
                    "a feed is probably missing", name, len(markers), before)
        return False
    digest = _digest(markers)
    aged = time.time() - _last_upload.get(name, 0.0)
    if _last_hash.get(name) == digest and aged < max_stale:
        return False              # unchanged: keep the ETag stable
    body = _encode(build_payload(markers))
    await asyncio.to_thread(_upload, name, body, cache_control)
    _last_hash[name] = digest
    _last_count[name] = len(markers)
    if name in CARRY_BUNDLES:
        _previous[name] = markers
    _last_upload[name] = time.time()
    _last_published[name] = datetime.now(UTC).isoformat(timespec="seconds")
    log.info("snapshot %s: published %d markers, %d bytes gzipped",
             name, len(markers), len(body))
    return True


async def _bundle_loop(name: str, kinds: set[str], interval: int,
                       cache_control: str, max_stale: int) -> None:
    """One bundle, forever. A failure never stops the loop, but it is
    always logged: this loop once swallowed an AttributeError every
    cycle for two days while the map served the last good object."""
    failures = 0
    while True:
        skipped = False
        try:
            # build_bundle returning None, or the drop guard, both mean
            # "not now": come back soon rather than after a whole cycle.
            shipped = await publish_once(name, kinds, cache_control, max_stale)
            skipped = not shipped and name not in _last_hash
            failures = 0
        except Exception:  # noqa: BLE001 - one bad cycle never stops the loop
            failures += 1
            # Every failure for the first few, then once a minute of
            # them: enough to alert on, not enough to flood the log.
            if failures <= 3 or failures % max(1, 60 // max(1, interval)) == 0:
                log.exception("snapshot %s: publish failed (%d in a row)", name, failures)
        await asyncio.sleep(min(RETRY_AFTER_SKIP_S, interval) if skipped else interval)


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


def _stale(name: str, interval: int) -> bool:
    """Whether this bundle has missed enough cycles to call it stuck.

    A bundle that has never published in this process is not stale yet:
    the process may have just started. One that published and then
    stopped, or that has been up for many cycles without ever managing
    one, is.
    """
    if not BUCKET:
        return False
    last = _last_upload.get(name)
    if last is None:
        return time.monotonic() - _started > max(STALE_CYCLES * interval, 300)
    return time.time() - last > STALE_CYCLES * interval


def status() -> dict:
    """Publisher health, surfaced on /api/warmup for ops.

    `stale` is the field to alert on. `published` alone is not enough:
    it is null after every deploy until the first successful cycle, so
    a monitor watching it either ignores a genuine stall or cries after
    every release.
    """
    return {
        "bucket": BUCKET or None,
        "schema": SCHEMA,
        "objects": {name: {"published": _last_published.get(name),
                           "hash": _last_hash.get(name, "")[:8] or None,
                           "stale": _stale(name, interval)}
                    for name, _kinds, interval, *_rest in BUNDLES},
        "stale": any(_stale(name, interval)
                     for name, _kinds, interval, *_rest in BUNDLES),
        "checked_at": time.time(),
    }
