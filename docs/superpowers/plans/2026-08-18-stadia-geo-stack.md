# Stadia Geo Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace CARTO tiles, the OSRM demo server, FOSSGIS Valhalla, and the Nominatim/Photon fallback with Stadia Maps so every geo dependency allows commercial use.

**Architecture:** Four independent PRs: tiles (URL swaps), routing (one new `valhalla.py` server module plus client conversions to Stadia's Valhalla endpoint), geocoding (single Stadia provider behind the offline gazetteer), docs. Browser calls are keyless via Stadia domain auth; server calls read env `STADIA_API_KEY` (Secret Manager `stadiamaps-api`).

**Tech Stack:** Python 3 / Starlette / httpx (mocked in tests), vanilla JS + Leaflet static pages, pytest, Playwright for page checks.

**Spec:** docs/superpowers/specs/2026-08-18-compliant-geo-stack-design.md

## Global Constraints

- Public repo: no secrets, no session links, no Claude-Session trailers in commits or PR bodies. Co-Authored-By line only.
- Prose style: Google developer style, no em or en dashes, no emoji.
- Every PR merges only after `gh pr checks --json state` shows SUCCESS with nothing PENDING/IN_PROGRESS/QUEUED.
- Env unset = fail soft to today's degraded behavior everywhere. CI and self-hosters never need a Stadia key.
- Tile URL: `https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png` (server side without `{r}`).
- Routing URL: `https://api.stadiamaps.com/route/v1` (Valhalla; POST JSON; `?api_key=` server side only).
- Geocoding URL: `https://api.stadiamaps.com/geocoding/v1/search` (Pelias).
- Attribution on all maps: `&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors` (plain text variant where the current line is plain).
- Windows tree is CRLF: use Read+Edit tools, never sed round-trips.

---

### Task 1 (PR "tiles" 1/2): client tile swap

**Files:**
- Modify: `src/ca_roads_demo/static/map.html:41-44` (preconnects), `:1128-1132` (tile layer + attribution)
- Modify: `src/ca_roads_demo/static/trip.html:148-149`
- Modify: `src/ca_roads_demo/static/watch.html:630-632`

**Interfaces:** none (static HTML).

- [ ] **Step 1: swap URLs.** In each file replace the `L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', ...)` URL with `https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png` and delete the `{s}` subdomain option if present. Replace the attribution string per Global Constraints (map.html keeps links, trip/watch keep plain text). In map.html replace the four cartocdn preconnect lines with one: `<link rel="preconnect" href="https://tiles.stadiamaps.com">`.
- [ ] **Step 2: verify.** `grep -rn "cartocdn" src/ca_roads_demo/static/` returns nothing. Serve locally (`uvicorn` demo app or python http.server on the static dir), load the map page from localhost, confirm tiles render (Stadia allows keyless localhost).
- [ ] **Step 3: commit** `feat: swap basemap tiles from CARTO to Stadia Maps`.

### Task 2 (PR "tiles" 2/2): server og compositor + CSP

**Files:**
- Modify: `src/ca_roads_demo/app.py` `fetch_tile` (~line 665-680) and CSP img-src block (~line 2187-2203)
- Test: `tests/test_site_assets.py` or nearest existing staticmap test file (search `grep -rn "staticmap\|fetch_tile" tests/`)

**Interfaces:** consumes env `STADIA_API_KEY`.

- [ ] **Step 1: failing tests.** New tests: (a) with `monkeypatch.setenv("STADIA_API_KEY", "k")`, the composed tile URL is `https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png` and the request carries `params={"api_key": "k"}` (capture via a fake `road.client.get`); (b) with the env unset, `fetch_tile` performs no HTTP call and returns `(tx, ty, None)` so the canvas composes the flat background.
- [ ] **Step 2: run, expect FAIL** (URL still cartocdn).
- [ ] **Step 3: implement.**

```python
_TILE_URL = "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}.png"

    async def fetch_tile(tx, ty):
        if not (0 <= ty < n):
            return tx, ty, None
        key = os.environ.get("STADIA_API_KEY", "").strip()
        if not key:
            return tx, ty, None
        try:
            resp = await road.client.get(
                _TILE_URL.format(z=z, x=tx % n, y=ty),
                params={"api_key": key},
                headers={"User-Agent": "ca-roads-mcp staticmap"},
                timeout=10,
            )
            return tx, ty, resp.content if resp.status_code == 200 else None
        except Exception:  # noqa: BLE001
            return tx, ty, None
```

- [ ] **Step 4: CSP.** In img-src remove `https://*.basemaps.cartocdn.com` and `https://*.cartocdn.com`, add `https://tiles.stadiamaps.com`. Update any CSP assertion in `tests/test_security_hardening.py` that names cartocdn.
- [ ] **Step 5: full test run** `python -m pytest -q` passes.
- [ ] **Step 6: commit, push branch `feat/stadia-tiles`, open PR, CI gate, merge.**

### Task 3 (PR "routing" 1/4): `valhalla.py` module

**Files:**
- Create: `src/ca_roads_demo/valhalla.py`
- Test: create `tests/test_valhalla.py`

**Interfaces (produced, used by Tasks 4-6):**
- `decode_polyline6(encoded: str) -> list[list[float]]` (lat, lon pairs)
- `async route(client, locations: list[dict], *, api_key: str, timeout: float = 20.0, **options) -> dict | None`: POSTs `{"locations": ..., "costing": "auto", **options}` to the routing URL with `params={"api_key": api_key}`. Returns the response `trip` dict, or None when routes are absent. Lets HTTP 400 raise `NoCandidateError` (caller widens search) and re-raises other non-200 via `resp.raise_for_status()`.
- `trip_points(trip: dict) -> list[list[float]]`: concatenated `decode_polyline6(leg["shape"])` for all legs.
- `trip_meters(trip: dict) -> float`: `trip["summary"]["length"] * 1000.0` (Valhalla default units are km).

- [ ] **Step 1: failing tests.** Round-trip test for the decoder (include a 10-line precision-6 encoder in the test file and assert decode(encode(pts)) == pts for `[[37.3382, -121.8863], [37.7749, -122.4194]]`); a `route()` test with a fake client asserting URL, api_key param, POST body shape, and trip passthrough; a 400 test asserting `NoCandidateError`; an empty-routes test asserting None.
- [ ] **Step 2: run, expect FAIL** (module missing).
- [ ] **Step 3: implement.**

```python
"""Stadia Maps Valhalla routing client shared by roadsnap and app."""
import httpx

ROUTE_URL = "https://api.stadiamaps.com/route/v1"
UA = {"User-Agent":
      "commutescout.com road snapper (https://commutescout.com)"}


class NoCandidateError(Exception):
    """Valhalla found no routable edge near an input location."""


def decode_polyline6(encoded: str) -> list[list[float]]:
    index = lat = lon = 0
    out: list[list[float]] = []
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        out.append([lat / 1e6, lon / 1e6])
    return out


async def route(client: httpx.AsyncClient, locations: list[dict], *,
                api_key: str, timeout: float = 20.0, **options):
    body = {"locations": locations, "costing": "auto", **options}
    resp = await client.post(ROUTE_URL, params={"api_key": api_key},
                             json=body, headers=UA, timeout=timeout)
    if resp.status_code == 400:
        raise NoCandidateError(resp.text[:200])
    resp.raise_for_status()
    trip = (resp.json() or {}).get("trip") or {}
    return trip if trip.get("legs") else None


def trip_points(trip: dict) -> list[list[float]]:
    pts: list[list[float]] = []
    for leg in trip.get("legs") or []:
        pts.extend(decode_polyline6(leg.get("shape") or ""))
    return pts


def trip_meters(trip: dict) -> float:
    return float((trip.get("summary") or {}).get("length") or 0) * 1000.0
```

- [ ] **Step 4: tests pass. Commit** `feat: add Stadia Valhalla routing client`.

### Task 4 (PR "routing" 2/4): roadsnap `_snap` and `_snap_toll`

**Files:**
- Modify: `src/ca_roads_demo/roadsnap.py` (`OSRM_URL` gone; `_snap` ~line 345; `_snap_toll` ~line 269)
- Test: `tests/test_roadsnap.py` (5 existing tests move to the new call shape)

**Interfaces:** consumes Task 3. `_snap`/`_snap_toll` signatures and return shapes unchanged; both read `os.environ["STADIA_API_KEY"]` and return None immediately when unset.

- [ ] **Step 1: failing tests first.** Rewrite the mocked responses in test_roadsnap.py from OSRM JSON (`routes[0].geometry.coordinates`) to Valhalla JSON (`trip.legs[].shape` polyline6, `trip.summary.length` in km). Encode test geometry with the encoder from tests/test_valhalla.py (import it or copy the helper). Add: env unset returns None without HTTP.
- [ ] **Step 2: implement `_snap`:** distance check unchanged; call `valhalla.route(client, [{"lat": lat1, "lon": lon1}, {"lat": lat2, "lon": lon2}], api_key=key)`; `NoCandidateError` and empty trip mean None; `dist = valhalla.trip_meters(trip)` with the same MAX_RATIO/MAX_EXTRA checks; points from `valhalla.trip_points(trip)` (already lat, lon: no swap), same decimation to <= 80 with tail append.
- [ ] **Step 3: implement `_snap_toll`:** locations gain `"heading": brg, "heading_tolerance": TOLL_BEARING_TOL, "radius": r` for r in (60, 150), widening on `NoCandidateError` (mirrors the old 400 loop) and raising `TransientSnapError` after both. On-route validation moves from OSRM steps to Valhalla maneuvers: for each leg maneuver, `names = " ".join(m.get("street_names", []) + m.get("begin_street_names", []))`, `d = float(m.get("length") or 0) * 1000.0` (km), same TOLL_ON_ROUTE_MIN ratio. Snapped endpoints come from the decoded shape: `pts[0]` and `pts[-1]` replace the OSRM waypoint locations in the net-bearing check and the returned `a`/`b`.
- [ ] **Step 4: full pytest passes. Commit** `feat: move road snapping from the OSRM demo server to Stadia Valhalla`.

### Task 5 (PR "routing" 3/4): app.py closure snap loop

**Files:**
- Modify: `src/ca_roads_demo/app.py` `_snap_closures_loop` (~line 1864-1893)

**Interfaces:** consumes Task 3.

- [ ] **Step 1:** replace the inline OSRM GET with `trip = await valhalla.route(road.client, [{"lat": c.begin_lat, "lon": c.begin_lon}, {"lat": c.end_lat, "lon": c.end_lon}], api_key=key)` inside the existing `contextlib.suppress(Exception)`; `coords = valhalla.trip_points(trip)` but note `_snap_path` expects lon, lat GeoJSON order, so pass `[[p[1], p[0]] for p in coords]` (check `_snap_path`'s consumption before deciding; keep its input contract unchanged). Distance km comes from `trip["summary"]["length"]`. Skip the whole fetch when env `STADIA_API_KEY` is unset (path stays None, closures render as dots). Keep the 1.1s pacing.
- [ ] **Step 2:** add or update the loop's test if one exists (`grep -rn "_snap_closures_loop\|CLOSURE_PATHS" tests/`). Full pytest passes. Commit `feat: closure stretch snapping via Stadia Valhalla`.

### Task 6 (PR "routing" 4/4): browser routing + CSP

**Files:**
- Modify: `src/ca_roads_demo/static/map.html` (`osrmRoute`/`valhallaRoute`/`anyRoute` ~1150-1210; `osrmDirections`/`valhallaDirections`/`anyDirections` ~3915-3985; `fmtOsrmStep`/`osrmToRoute` become dead, delete)
- Modify: `src/ca_roads_demo/static/watch.html:820-827` plus a pasted `decodePolyline6`
- Modify: `src/ca_roads_demo/app.py` CSP connect-src (~line 2208-2210)

**Interfaces:** none new; keyless browser calls under domain auth.

- [ ] **Step 1: map.html.** Point `valhallaRoute` and `valhallaDirections` at Stadia via POST:

```javascript
const VALHALLA_URL = 'https://api.stadiamaps.com/route/v1';
// inside each function
const res = await fetch(VALHALLA_URL, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(req),
  signal: AbortSignal.timeout(8000),
});
```

`anyRoute` and `anyDirections` become Valhalla-only (try/catch to null). Delete `osrmRoute`, `osrmDirections`, `osrmToRoute`, `fmtOsrmStep`, and the 500 ms inter-provider sleep in `roadSnap`. Response handling is already Valhalla-shaped and stays.
- [ ] **Step 2: watch.html.** Replace the OSRM fetch in the `rw-preview` handler with the same POST (locations from `a`/`b`), paste `decodePolyline6` from map.html:1168-1184 above it, and set `routePts = decodePolyline6(route.trip.legs[0].shape)` (multi-leg flatMap like map.html for safety). Error copy stays.
- [ ] **Step 3: CSP.** connect-src: remove `https://router.project-osrm.org` and `https://valhalla1.openstreetmap.de`, add `https://api.stadiamaps.com`. Update tests naming those hosts.
- [ ] **Step 4: verify.** `grep -rn "project-osrm\|valhalla1" src/` returns nothing. Playwright from localhost: plan a route on the map page, confirm a road-following polyline draws and `roadinfo` fills; watch page route preview draws. Full pytest passes.
- [ ] **Step 5: commit, push branch `feat/stadia-routing`, PR, CI gate, merge.**

### Task 7 (PR "geocoding"): geocode.py single provider

**Files:**
- Modify: `src/ca_roads_mcp/geocode.py`
- Test: `tests/test_geocode.py` (12 tests)

**Interfaces:** public `geocode()` and `geocode_candidates()` signatures unchanged. Consumes env `STADIA_API_KEY`.

- [ ] **Step 1: failing tests.** Rework mocks from Nominatim/Photon JSON to Pelias GeoJSON (`features[].geometry.coordinates` lon-lat, `properties.label/name/region_a`). Keep the behavioral tests: gazetteer first, plausibility rejection, cache, definitive-miss caching, ladder ("X, California" then raw), trailing-word trim retry, candidates near-bias. Add: env unset performs no HTTP and does not cache a definitive miss.
- [ ] **Step 2: implement.** Delete `NOMINATIM_URL`, `PHOTON_URL`, `_search`, `_search_photon`, `_photon_hits`, THROTTLE default drops to 0.0 (keep the variable and lock for the tests that set it). New provider:

```python
STADIA_URL = "https://api.stadiamaps.com/geocoding/v1/search"
# lon_min, lat_max, lon_max, lat_min (kept from the Nominatim viewbox)
_RECT = (-124.6, 42.1, -114.0, 32.4)


async def _search_stadia(
    client: httpx.AsyncClient,
    q: str,
    near: tuple[float, float] | None = None,
    limit: int = 1,
) -> list[tuple[float, float, str]] | None:
    """Stadia (Pelias) search inside the California rectangle. Returns
    hits, [] for a clean miss, None for network trouble or no key."""
    key = os.environ.get("STADIA_API_KEY", "").strip()
    if not key:
        return None
    params = {
        "text": q, "size": limit, "api_key": key,
        "boundary.country": "US",
        "boundary.rect.min_lon": _RECT[0],
        "boundary.rect.max_lat": _RECT[1],
        "boundary.rect.max_lon": _RECT[2],
        "boundary.rect.min_lat": _RECT[3],
    }
    if near:
        params["focus.point.lat"], params["focus.point.lon"] = near
    try:
        resp = await client.get(STADIA_URL, params=params,
                                headers={"User-Agent": USER_AGENT},
                                timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except Exception:  # noqa: BLE001 - failure means "use the fallback"
        return None
    out: list[tuple[float, float, str]] = []
    for f in features:
        lon, lat = (f.get("geometry", {}).get("coordinates") or [None, None])[:2]
        if lat is None or not _plausible({"lat": lat, "lon": lon}):
            continue
        props = f.get("properties", {})
        out.append((float(lat), float(lon),
                    props.get("label") or props.get("name") or ""))
    return out
```

`geocode()` ladder: for each candidate query call `_search_stadia`; None means network trouble (sets `saw_network_failure`), non-empty first hit wins; after the ladder, one trailing-word-trim retry replaces the Photon retry. `geocode_candidates()` calls `_search_stadia(client, q, near=near, limit=limit)` and dedupes as it does today. Rewrite the module docstring (Nominatim policy paragraph goes away; note the gazetteer-first design and env-unset behavior).
- [ ] **Step 3: full pytest passes** (MCP suite included). Commit, push `feat/stadia-geocoding`, PR, CI gate, merge.

### Task 8 (PR "docs"): privacy, runbook, licenses

**Files:**
- Modify: `src/ca_roads_demo/static/privacy.html` (third-party processor list)
- Modify: `docs/deploy.md`, `docs/architecture.md` and `docs/data-sources.md` where they name CARTO/OSRM/Nominatim (`grep -rn "CARTO\|OSRM\|Nominatim\|Photon\|cartocdn" docs/ src/ca_roads_demo/static/privacy.html README.md`)

**Interfaces:** none.

- [ ] **Step 1: privacy.** Replace the tile/routing/geocoding provider sentences: Stadia Maps receives tile requests (visitor IP), routing requests (route endpoints), and geocoding queries. Keep effective-date bump per that page's convention.
- [ ] **Step 2: deploy.md.** Document `STADIA_API_KEY` mounted from secret `stadiamaps-api` on BOTH services via `--update-secrets`, and the dashboard domain-allowlist step for a self-hoster's own domain.
- [ ] **Step 3: WZDx license check.** Fetch the three feeds' registry entries (FHWA WZDx feed registry rows for MD, HI, FL) and record license + any attribution wording in docs/data-sources.md.
- [ ] **Step 4: sweep.** `grep -rni "cartocdn\|project-osrm\|valhalla1\|nominatim\|photon" src/ docs/ README.md site/` finds only historical spec/plan docs. Commit, push `docs/stadia-cutover`, PR, CI gate, merge.

### Task 9: release and deploy

- [ ] **Step 1:** bump `pyproject.toml` and `server.json` together (minor bump), release PR, merge, `gh release create`.
- [ ] **Step 2: deploy demo** (all flags explicit): `gcloud run deploy ca-roads-demo --source . --project ca-roads-mcp --region us-west1 --service-account ca-roads-run@ca-roads-mcp.iam.gserviceaccount.com --min-instances 1 --max-instances 1 --concurrency 20 --memory 1Gi --cpu 1 --update-secrets STADIA_API_KEY=stadiamaps-api:latest` (command per docs/deploy.md; NEVER --set-env-vars/--set-secrets).
- [ ] **Step 3: deploy mcp** similarly (`--min-instances 0 --max-instances 1 --concurrency 40 --update-secrets STADIA_API_KEY=stadiamaps-api:latest`).
- [ ] **Step 4: prod verification.** Site tiles 200 from a map page; plan a route on the live planner; create a trip and confirm its og image renders roads; one MCP geocode call for a non-gazetteer landmark; devtools console free of CSP violations; /api/stats and /api/mapdata latency probe unchanged; demo env listing shows all prior keys plus STADIA_API_KEY.
- [ ] **Step 5:** two-day Stadia usage dashboard check; memory update; remind Nic of the Starter subscription deadline (~2026-09-01).
