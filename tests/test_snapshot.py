"""Snapshot publisher: what gets published, and what must not be."""
import gzip
import json

from ca_roads_demo import snapshot

# The one hostname the page, the service worker and the CSP must
# all agree on.
SNAP_HOST = "data.commutescout.com"


def test_payload_carries_the_fields_the_client_depends_on():
    p = snapshot.build_payload([{"kind": "incident", "lat": 1, "lon": 2}])
    # schema drives the long-lived-tab self-reload; published drives the
    # "data as of" chip. Losing either breaks a kiosk silently.
    assert p["schema"] == snapshot.SCHEMA
    assert p["published"].endswith("+00:00")
    assert p["degraded"] is False
    assert len(p["markers"]) == 1


def test_encode_is_gzip_and_round_trips():
    body = snapshot._encode(snapshot.build_payload([{"a": 1}]))
    assert body[:2] == b"\x1f\x8b"                  # gzip magic
    assert json.loads(gzip.decompress(body))["markers"] == [{"a": 1}]


def test_digest_covers_markers_and_ignores_the_timestamp():
    """The whole 304 economy rests on this. If the digest included
    `published` it would change every cycle, rotate the GCS ETag, and
    make every open map re-download the object on every poll."""
    a = snapshot._digest([{"kind": "incident", "lat": 1}])
    b = snapshot._digest([{"kind": "incident", "lat": 1}])
    c = snapshot._digest([{"kind": "incident", "lat": 2}])
    assert a == b and a != c
    # Two payloads built a moment apart differ in `published` alone;
    # the digest must not notice.
    p1 = snapshot.build_payload([{"kind": "incident", "lat": 1}])
    p2 = snapshot.build_payload([{"kind": "incident", "lat": 1}])
    assert snapshot._digest(p1["markers"]) == snapshot._digest(p2["markers"])


async def test_skips_publishing_while_feeds_are_warming(monkeypatch):
    """D2: never publish an incomplete build. A warming instance would
    otherwise overwrite a good snapshot with a nearly-empty map for
    every visitor at once."""
    from ca_roads_demo import app as demo_app

    async def half_warm(box, want, **kw):
        return [{"kind": "incident"}], 3, 9, False

    monkeypatch.setattr(demo_app, "build_markers", half_warm)
    assert await snapshot.build_bundle("live.json.gz", {"incident"}) is None


async def test_skips_publishing_a_degraded_build(monkeypatch):
    from ca_roads_demo import app as demo_app

    async def degraded(box, want, **kw):
        return [{"kind": "incident"}], 9, 9, True

    monkeypatch.setattr(demo_app, "build_markers", degraded)
    assert await snapshot.build_bundle("live.json.gz", {"incident"}) is None


async def test_publishes_a_healthy_build_and_applies_slim(monkeypatch):
    from ca_roads_demo import app as demo_app

    async def healthy(box, want, **kw):
        # A closure with stretch geometry and a null field: slim must
        # drop both, exactly as the endpoint does.
        return ([{"kind": "lane_closure", "lat": 1, "lon": 2,
                  "path": [[1, 2], [3, 4]], "end": [3, 4],
                  "county": None, "route": "I-80"}], 9, 9, False)

    monkeypatch.setattr(demo_app, "build_markers", healthy)
    markers = await snapshot.build_bundle("live.json.gz", {"closure"})
    m = markers[0]
    assert "path" not in m and "end" not in m and "county" not in m
    assert m["route"] == "I-80"


async def test_unchanged_payload_is_not_reuploaded(monkeypatch):
    """An unchanged upload would rotate the GCS ETag and turn every
    client's cheap 304 poll into a full download."""
    from ca_roads_demo import app as demo_app

    async def healthy(box, want, **kw):
        return [{"kind": "incident", "lat": 1, "lon": 2}], 9, 9, False

    uploads = []

    def fake_upload(name, body, cc):
        uploads.append(name)

    monkeypatch.setattr(demo_app, "build_markers", healthy)
    monkeypatch.setattr(snapshot, "_upload", fake_upload)
    monkeypatch.setattr(snapshot, "_last_hash", {})
    monkeypatch.setattr(snapshot, "_last_upload", {})
    monkeypatch.setattr(snapshot, "BUCKET", "test-bucket")

    # First cycle ships.
    assert await snapshot.publish_once("live.json.gz", {"incident"}, "cc", 60)
    assert uploads == ["live.json.gz"]
    # Second cycle, identical markers, still inside max_stale: no write,
    # so the ETag holds and every client poll in between is a 304.
    assert not await snapshot.publish_once("live.json.gz", {"incident"},
                                           "cc", 60)
    assert uploads == ["live.json.gz"]


async def test_unchanged_payload_refreshes_once_it_passes_max_stale(monkeypatch):
    """Quiet data must not make a healthy publisher look dead: the
    object is re-stamped once it ages past max_stale so the client's
    "data as of" chip stays honest."""
    from ca_roads_demo import app as demo_app

    async def healthy(box, want, **kw):
        return [{"kind": "incident", "lat": 1, "lon": 2}], 9, 9, False

    uploads = []
    monkeypatch.setattr(demo_app, "build_markers", healthy)
    monkeypatch.setattr(snapshot, "_upload",
                        lambda n, b, c: uploads.append(n))
    monkeypatch.setattr(snapshot, "_last_hash", {})
    monkeypatch.setattr(snapshot, "_last_upload", {})
    monkeypatch.setattr(snapshot, "BUCKET", "test-bucket")

    await snapshot.publish_once("live.json.gz", {"incident"}, "cc", 60)
    snapshot._last_upload["live.json.gz"] -= 61      # pretend a minute passed
    assert await snapshot.publish_once("live.json.gz", {"incident"}, "cc", 60)
    assert len(uploads) == 2


async def test_run_is_a_noop_without_a_bucket(monkeypatch):
    """Local dev and CI must never reach for GCS credentials."""
    monkeypatch.setattr(snapshot, "BUCKET", "")
    called = []
    monkeypatch.setattr(snapshot, "_client", lambda: called.append(1))
    await snapshot.run()
    assert not called


def test_bundles_cover_every_layer_the_map_renders():
    """A kind that lands in no bundle silently disappears from the map
    once the boot path stops calling /api/mapdata."""
    published = set()
    for _name, kinds, *_rest in snapshot.BUNDLES:
        published |= kinds
    assert published == {"incident", "closure", "chain", "fire", "toll",
                         "sign", "rwis", "camera"}


def test_live_bundle_is_the_fast_one():
    names = [n for n, *_rest in snapshot.BUNDLES]
    assert names[0] == "live.json.gz"
    live = next(b for b in snapshot.BUNDLES if b[0] == "live.json.gz")
    assert live[2] == 30                       # seconds between builds
    assert "max-age=15" in live[3]
    assert "stale-while-revalidate=180" in live[3]
    # Tight enough that the chip stays green while the publisher is up.
    assert live[4] <= 120


def test_csp_allows_the_snapshot_host():
    """The CSP must allow connecting to the snapshot host.

    This one is worth pinning because the failure is invisible: with the
    host missing from connect-src the browser blocks the fetch, the
    client falls back to /api/mapdata, and the map keeps working while
    quietly using the slow path it was migrated off. It cost a round of
    measurement to notice.
    """
    from starlette.testclient import TestClient

    from ca_roads_demo import app as demo_app

    csp = TestClient(demo_app.app).get("/map").headers["content-security-policy"]
    connect = next(d for d in csp.split(";") if d.strip().startswith("connect-src"))
    host = "https://" + SNAP_HOST
    assert host in connect, f"{host} missing from {connect!r}"


def test_client_and_csp_agree_on_the_snapshot_host():
    """The page hardcodes the host it fetches from; the CSP has to name
    the same one. Two places, so they can drift."""
    import pathlib
    import re

    html = pathlib.Path(
        "src/ca_roads_demo/static/map.html").read_text(encoding="utf-8")
    base = re.search(r"const SNAP_BASE = '([^']+)'", html).group(1)
    assert base == "https://" + SNAP_HOST

    sw = pathlib.Path(
        "src/ca_roads_demo/static/sw.js").read_text(encoding="utf-8")
    assert re.search(r"const SNAP_HOST = '([^']+)'", sw).group(1) == SNAP_HOST


def test_service_worker_is_never_edge_cached():
    """A worker snapshots its CSP at install. An edge-cached sw.js kept
    installing workers whose connect-src predated the snapshot host, so
    they could not fetch snapshots at all while the page could."""
    from starlette.testclient import TestClient

    from ca_roads_demo import app as demo_app

    r = TestClient(demo_app.app).get("/sw.js")
    assert r.status_code == 200
    assert "no-cache" in r.headers.get("cache-control", "")


def test_state_counts_are_current():
    """Every hardcoded "N states" must match the live registry.

    The count is written in the page metadata, the assistant prompt, the
    MCP tool docstring, the README, and the homepage's stats module. They
    drift the moment a state is added, and the MCP docstring drifting is
    the expensive one: the model reads it to decide whether a location is
    worth querying.
    """
    import pathlib
    import re

    from ca_roads_demo import states

    actual = states.coverage_summary()["states"]
    assert actual > 0

    checked = 0
    for path, pattern in (
        ("src/ca_roads_demo/static/map.html", r"across (\d+) states"),
        ("src/ca_roads_demo/prompt.py", r"\((\d+) states, not just California\)"),
        ("src/ca_roads_mcp/server.py", r"just California: (\d+) states today"),
        ("README.md", r"across \*\*(\d+) states\*\*|across (\d+) states"),
        ("docs/registry.md", r"across (\d+) states"),
        ("site/lib/stats.ts", r"STATE_COUNT = (\d+)"),
    ):
        text = pathlib.Path(path).read_text(encoding="utf-8")
        found = [int(g) for m in re.finditer(pattern, text)
                 for g in m.groups() if g]
        assert found, f"no state count found in {path}"
        for n in found:
            assert n == actual, f"{path} says {n} states, registry says {actual}"
        checked += len(found)
    assert checked >= 6


def test_feed_counts_are_current():
    """Sibling to test_state_counts_are_current: every hardcoded "N
    official agency feeds" claim must match states.PUBLIC_SOURCE_COUNT.
    Before this test, stats-1.tsx's own comment claimed a drift guard
    existed that in fact only checked states, not feeds - this closes
    that gap.

    This pins to PUBLIC_SOURCE_COUNT, not states.coverage_summary()
    ["sources"]: the live registry count is environment-dependent by
    design (_wzdx_superseded drops a WZDx entry once a keyed feed
    supersedes it, so a keyless checkout counts more sources than
    production, which runs with keys configured and truthfully serves
    fewer). PUBLIC_SOURCE_COUNT is the number production actually shows;
    see its docstring in states.py for the update procedure.
    """
    import pathlib
    import re

    from ca_roads_demo import states

    actual = states.PUBLIC_SOURCE_COUNT
    assert actual > 0

    checked = 0
    for path, pattern in (
        ("README.md", r"reads (\d+) official agency feeds"),
        ("site/lib/stats.ts", r"AGENCY_FEED_COUNT = (\d+)"),
        ("site/app/about/page.tsx", r"reads (\d+) official agency feeds"),
        ("site/components/blocks/hero-section-1.tsx",
         r"reads (\d+) official agency feeds"),
        ("site/app/data-sources/page.tsx",
         r"reads (\d+) official agency feeds"),
    ):
        text = pathlib.Path(path).read_text(encoding="utf-8")
        found = [int(g) for m in re.finditer(pattern, text)
                 for g in m.groups() if g]
        assert found, f"no feed count found in {path}"
        for n in found:
            assert n == actual, f"{path} says {n} feeds, PUBLIC_SOURCE_COUNT says {actual}"
        checked += len(found)
    assert checked >= 5
