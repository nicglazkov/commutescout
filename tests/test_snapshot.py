"""Snapshot publisher: what gets published, and what must not be.

Also home to the published-claim drift guards (state count, feed count,
tool count), which live here because they read the same registry the
publisher does.
"""
import gzip
import json
import re
import time

import pytest

from ca_roads_demo import snapshot
from mapsrc import map_source

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
                         "sign", "rwis", "camera", "plugin"}


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

    html = map_source()
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
        # The same file states coverage twice; both must agree. This one
        # said 32 while the line above said 38, inside the text the
        # assistant reads to answer users.
        ("src/ca_roads_demo/prompt.py", r"(\d+) covered states"),
        ("src/ca_roads_mcp/server.py", r"just California: (\d+) states today"),
        ("README.md", r"across \*\*(\d+) states\*\*|across (\d+) states"),
        # Two counts in this file, and the long connector description
        # says "across N US states" with the wrap falling between "US"
        # and "states". A pattern anchored on "states" saw only the short
        # description, so the long one sat at 32 while the rest said 37.
        ("docs/registry.md", r"across (\d+) (?:US\b|states)"),
        ("site/lib/stats.ts", r"STATE_COUNT = (\d+)"),
        # The marketing pages state it in prose, outside stats.ts, so the
        # constant alone was not enough to keep them honest.
        ("site/app/page.tsx", r"across (\d+) states"),
        ("site/components/blocks/hero-section-1.tsx", r"across (\d+) states"),
        ("docs/architecture.md", r"(\d+) states"),
        ("docs/mcp.md", r"(\d+) states, not just California"),
        # /mcp states the count inside the get_nearby_events blurb. It
        # used to be split across a string concatenation, which hid it
        # from every per-file pattern; the blurb now keeps "37 states"
        # on one line so this sees it.
        ("site/app/mcp/page.tsx", r"(\d+) states"),
        # The registry listing is the one nobody sees drift: it is served
        # by modelcontextprotocol.io, not by us.
        ("server.json", r"(\d+) US states"),
    ):
        text = pathlib.Path(path).read_text(encoding="utf-8")
        found = [int(g) for m in re.finditer(pattern, text)
                 for g in m.groups() if g]
        assert found, f"no state count found in {path}"
        for n in found:
            assert n == actual, f"{path} says {n} states, registry says {actual}"
        checked += len(found)
    assert checked >= 10


def test_no_stale_state_count_in_the_built_site():
    """Scan the export, not the sources.

    The per-file patterns above read raw source, so a count split across
    a line ("...state, 38 " + "states, ...") is invisible to them. That is
    exactly how /mcp kept claiming 38 after every other surface moved to
    37. The built HTML has the concatenation resolved, so this catches
    any phrasing anywhere on any page.
    """
    import pathlib
    import re

    import pytest

    from ca_roads_demo import states

    out = pathlib.Path("site/out")
    if not out.exists():
        pytest.skip("site/out is not built; CI's site job builds first.")

    actual = states.coverage_summary()["states"]
    bad = []
    for page in out.glob("*.html"):
        text = page.read_text(encoding="utf-8", errors="replace")
        for found in re.findall(r"(\d+)\s+states", text):
            if int(found) != actual:
                bad.append(f"{page.name} says {found} states")
    assert not bad, f"registry says {actual}: {sorted(set(bad))}"


def test_state_count_matches_the_published_matrix():
    """The number we claim must equal the rows a visitor can count.

    /data-sources renders one row per state. The claim was 38 while the
    matrix had 37 rows, because coverage_summary counted source labels
    and Texas ships three feeds under two labels ("Texas" for the toll
    feeds, "Texas (Austin)" for the work-zone feed).
    """
    import pathlib
    import re

    from ca_roads_demo import states

    md = pathlib.Path("docs/state-coverage.md").read_text(encoding="utf-8")
    rows = [ln for ln in md.splitlines()
            if ln.startswith("|") and not re.match(r"^\|[\s:-]+\|", ln)]
    documented = len(rows) - 1  # minus the header
    assert states.coverage_summary()["states"] == documented

    ts = pathlib.Path("site/lib/state-coverage.ts").read_text(encoding="utf-8")
    assert len(re.findall(r"\{\s*state:\s*[\"']", ts)) == documented


def test_sub_region_labels_do_not_inflate_the_state_count():
    """A "State (Region)" label is the same state as "State"."""
    from ca_roads_demo import states

    assert states._state_key("Texas (Austin)") == "Texas"
    assert states._state_key("Texas") == "Texas"
    assert states._state_key("California") == "California"


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


# The developer-facing and plugin pages carry no count today, but they
# describe the same coverage as the marketing pages and are where a
# "across N states" or "N official agency feeds" line tends to get
# added later. The two tests above demand at least one match per file,
# which would make adding such a page a failing test rather than a
# guarded one; this one checks whatever counts a page happens to state
# and passes when it states none.
OPTIONAL_COUNT_PAGES = (
    "site/app/developers/page.tsx",
    "site/app/mcp/page.tsx",
    "site/app/plugins/page.tsx",
    "site/app/marketplace/page.tsx",
    "site/app/pricing/page.tsx",
    # /pricing renders this block, which interpolates lib/stats.ts.
    "site/components/blocks/pricing-1.tsx",
)


def test_site_pages_state_and_feed_counts_agree_when_stated():
    """Any count these pages do state must be the current one."""
    import pathlib
    import re

    from ca_roads_demo import states

    state_count = states.coverage_summary()["states"]
    feed_count = states.PUBLIC_SOURCE_COUNT

    bad = []
    for rel in OPTIONAL_COUNT_PAGES:
        text = pathlib.Path(rel).read_text(encoding="utf-8")
        for n in re.findall(r"(\d+)\s+states\b", text):
            if int(n) != state_count:
                bad.append(f"{rel} says {n} states, registry says {state_count}")
        for n in re.findall(r"(\d+)\s+(?:official agency )?feeds\b", text):
            if int(n) != feed_count:
                bad.append(
                    f"{rel} says {n} feeds, PUBLIC_SOURCE_COUNT says {feed_count}")
    assert not bad, sorted(bad)


# "ten tools" is written in words as often as in digits, so the guard
# reads both. Anything else a page might say ("the tools", "new tools")
# carries no count and is left alone.
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12,
}
TOOL_COUNT_RE = re.compile(
    r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(?:read-only\s+|MCP\s+)?tools\b",
    re.IGNORECASE,
)


def test_tool_counts_are_current():
    """Every prose "ten tools" claim must match the tool registry.

    Sibling to the state and feed guards. The count is claimed in the
    README feature list, the architecture diagram, and three places on
    /mcp plus two on /developers, which is exactly the spread that let
    docs/mcp.md sit at nine tools while README said ten. The source of
    truth is the same one tests/test_api_reference.py uses: the tool
    list that scripts/gen_api_reference.py builds from the tools' own
    schemas.
    """
    import pathlib
    import runpy

    repo = pathlib.Path(__file__).resolve().parent.parent
    build = runpy.run_path(
        str(repo / "scripts" / "gen_api_reference.py"), run_name="not_main"
    )["build"]
    actual = len(build()["tools"])
    assert actual > 0

    paths = [repo / "README.md", repo / "EVALS.md"]
    paths += sorted((repo / "docs").glob("*.md"))
    paths += sorted((repo / "site" / "app").glob("**/page.tsx"))

    bad = []
    checked = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for m in TOOL_COUNT_RE.finditer(text):
            token = m.group(1).lower()
            n = NUMBER_WORDS.get(token) or int(token)
            checked += 1
            if n != actual:
                bad.append(
                    f"{path.relative_to(repo).as_posix()} says "
                    f"{m.group(0)!r}, the registry has {actual}")
    assert not bad, sorted(bad)
    # The claim is made on several surfaces; if it vanishes everywhere
    # the guard has stopped guarding anything.
    assert checked >= 5, f"only {checked} tool-count claims found"


@pytest.mark.asyncio
async def test_a_chain_control_becomes_a_marker_and_does_not_break_the_bundle(monkeypatch):
    """The live bundle carries chain controls, and a marker built from one
    read a field the model does not have. Nothing caught it because the
    feed is empty outside chain season: the first control of the winter
    made every live publish raise, silently, and the map served the last
    good object for as long as that lasted. The test builds one rather
    than trusting the feed to be non-empty."""
    from ca_roads.models import ChainControl
    from ca_roads_demo import app as demo_app

    control = ChainControl(
        index="x", district=3, route="I-80", county="Placer", direction="EB",
        location_name="Kingvale", nearby_place="Soda Springs", lat=39.31, lon=-120.36,
        in_service=True, status="R-2", status_description="Chains required",
        status_updated_at=None,
    )

    class _Result:
        records = [control]
        degraded = False

    async def fake_chain_controls():
        return _Result()

    road = demo_app.tools.get_road()
    monkeypatch.setattr(road, "chain_controls", fake_chain_controls)
    markers, _ready, _total, _degraded = await demo_app.build_markers(
        (-85.0, -180.0, 85.0, 180.0), {"chain"})
    chains = [m for m in markers if m["kind"] == "chain_control"]
    assert len(chains) == 1, chains
    assert chains[0]["label"] == "Chains required"
    assert chains[0]["status"] == "R-2" and chains[0]["route"] == "I-80"
    # The publisher encodes what it built; this is the step that raised.
    assert demo_app.shape_markers(markers, slim=True)


def test_a_stuck_bundle_is_visible_without_reading_the_log(monkeypatch):
    """`published` is null after every deploy, so a monitor cannot tell a
    fresh process from a stuck one. `stale` can: it stays false while a
    young process is still getting started and turns true once a bundle
    has missed enough cycles."""
    monkeypatch.setattr(snapshot, "BUCKET", "example-bucket")
    monkeypatch.setattr(snapshot, "_last_upload", {})
    monkeypatch.setattr(snapshot, "_last_published", {})
    # A process that started seconds ago has published nothing yet.
    monkeypatch.setattr(snapshot, "_started", time.monotonic())
    assert snapshot.status()["stale"] is False
    # One that has been up for an hour with nothing published is stuck.
    monkeypatch.setattr(snapshot, "_started", time.monotonic() - 3600)
    st = snapshot.status()
    assert st["stale"] is True and st["objects"]["live.json.gz"]["stale"] is True
    # A bundle that published recently is not stale.
    monkeypatch.setattr(snapshot, "_last_upload", {n: time.time() for n, *_ in snapshot.BUNDLES})
    assert snapshot.status()["stale"] is False


def test_the_registry_manifest_fits_what_the_registry_accepts():
    """server.json is published to the MCP Registry, which rejects a
    description over 100 characters. Ours was 152 for months: every
    publish failed validation, so the listing sat at an old version
    describing the service as California-only. The limit is checked here
    rather than discovered at publish time."""
    import json
    import pathlib

    manifest = json.loads(pathlib.Path("server.json").read_text(encoding="utf-8"))
    assert len(manifest["description"]) <= 100, len(manifest["description"])
    assert manifest["name"] == "io.github.nicglazkov/commutescout"
    # The schema the publisher validates against moves; a deprecated one
    # is a warning today and a rejection later.
    assert manifest["$schema"].endswith("/2025-12-11/server.schema.json")
    # The published version is what the release chain bumped.
    import tomllib

    pyproject = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["version"] == pyproject["project"]["version"]
