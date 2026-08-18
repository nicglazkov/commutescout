# Compliant geo stack: Stadia Maps for tiles, routing, and geocoding

Date: 2026-08-18. Status: approved direction, spec for review.

## Goal

Replace the three third party geo dependencies whose terms do not allow
commercial use with Stadia Maps, a single commercially licensed vendor,
so the product can charge money without violating any provider's terms.

## Background: what is non compliant today

| Dependency | Terms problem | Usage sites |
| --- | --- | --- |
| CARTO basemap tiles | Free tier is non commercial; commercial use needs an enterprise contract | `map.html:1128`, `trip.html:148`, `watch.html:630`, server side og image compositor `app.py` (`_STATICMAP` tile fetch), CSP img-src, 4 preconnect hints |
| OSRM demo server (router.project-osrm.org) | Community capacity, "shall not be behind a paywall" | `map.html` (2 call sites), `watch.html:820`, `roadsnap.py` (`OSRM_URL`), `app.py` `_snap_closures_loop` |
| FOSSGIS Valhalla (valhalla1.openstreetmap.de) | Commercial use barred when routing is a substantial feature | `map.html` (2 call sites) |
| Nominatim public instance + Photon (komoot.io) | Nominatim policy requires running your own service when geocoding is a primary function; Photon public instance has no commercial guarantee | `geocode.py` network fallback (MCP package) |

Everything else in the external host inventory was re checked on
2026-08-18 and is compliant. See the compliance appendix.

## Non goals

- No change to any state DOT or federal data feed.
- No switch from raster to vector tiles. Raster keeps the swap to a URL
  change and the existing Leaflet code untouched.
- No self hosting. Decided against a VM on cost and ops grounds.
- No map restyle. The Stadia style closest to CARTO Voyager ships
  first; restyling later is a one line change per page.

## Vendor decision

Stadia Maps, one account for all three services.

- Plan: account created 2026-08-18 on a 14 day trial of the
  Professional plan ($250/mo tier, no payment form). ACTION: subscribe
  to Starter ($20/mo, commercial use allowed, 1M credits/mo) before the
  trial ends around 2026-09-01. The free tier is non commercial, so
  letting the trial lapse without subscribing reintroduces the exact
  problem this project removes.
- Verified live on 2026-08-18 with the staged key: raster tiles 200,
  geocoding 200, Valhalla routing 200. Domain auth verified: keyless
  tile request with Origin commutescout.com gets 200, keyless request
  with no Origin gets 401. Observed: requests with an arbitrary
  unregistered Origin are also accepted. That is Stadia's abuse surface
  rather than ours, but it means origin spoofing against our name is
  possible; the mitigation is usage monitoring, below.
- Credit model: raster tile 1 credit, routing 20, geocoding 20, static
  map 20. Current traffic is far below the Starter allowance. Overage
  degrades gracefully (3 cents per 1k credits) instead of cutting off.

## Authentication

- Browser: domain based auth. commutescout.com is allowlisted in the
  Stadia dashboard. No key ships in HTML or JS. Local development and
  Playwright work keyless from localhost (rate limited by Stadia).
- Server: API key in Secret Manager secret `stadiamaps-api`, mounted as
  env `STADIA_API_KEY` on BOTH Cloud Run services (demo needs it for
  the og image compositor and closure snapping; MCP needs it for
  geocoding). The runtime SA already has accessor on the secret.
- Every deploy uses `--update-secrets STADIA_API_KEY=stadiamaps-api:latest`
  (merge semantics, never `--set-secrets`).

## Design

Four small PRs, in this order.

### PR 1: tiles

- Swap the Leaflet tile layer in `map.html`, `trip.html`, and
  `watch.html` to
  `https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png`.
  Alidade Smooth is the light, low saturation style closest to Voyager.
  The `{r}` retina suffix is supported by Stadia's raster endpoint.
- Attribution string on all three maps becomes:
  `&copy; Stadia Maps &copy; OpenMapTiles &copy; OpenStreetMap contributors`
  (linked forms on `map.html` where the current line has links).
- `app.py` og image compositor: tile URL becomes the Stadia raster URL
  with `?api_key={STADIA_API_KEY}`. When the env is unset the existing
  behavior already degrades to the flat background color; keep that.
- Preconnect hints: the four cartocdn hosts collapse to one
  `https://tiles.stadiamaps.com`.
- CSP img-src: remove `https://*.basemaps.cartocdn.com` and
  `https://*.cartocdn.com`, add `https://tiles.stadiamaps.com`.

### PR 2: routing

All routing converges on Stadia's Valhalla endpoint
`https://api.stadiamaps.com/route/v1`.

- `map.html`: the two existing Valhalla call sites port nearly as is
  (same request JSON, same polyline6 response shape; the page already
  decodes polyline6). The two OSRM call sites convert to the same
  Valhalla request and reuse that decoder. Browser calls are keyless
  under domain auth.
- `watch.html` route preview: same conversion, keyless. This page has
  no polyline6 decoder today (its call is OSRM GeoJSON), so it gets a
  copy of the small `decodePolyline6` function from `map.html`.
- `roadsnap.py`: `OSRM_URL` GET with GeoJSON geometry becomes a keyed
  Valhalla POST. Add a small pure Python polyline6 decoder (about 20
  lines, unit tested). Distance comes from `trip.summary.length`. The
  existing sanity checks (MIN/MAX meters, MAX_RATIO, transient retry
  budget) stay unchanged.
- `app.py` `_snap_closures_loop`: same keyed Valhalla conversion,
  sharing the decoder and response mapping with roadsnap (one helper,
  imported by both). The 1.1s pacing stays; it is harmless and kind.
- Fail soft: env unset or Stadia unreachable keeps today's behavior
  (closures render as dots or short straight segments; transient
  retries in roadsnap still apply).
- CSP connect-src: remove `https://router.project-osrm.org` and
  `https://valhalla1.openstreetmap.de`, add
  `https://api.stadiamaps.com`.

### PR 3: geocoding

- `geocode.py`: the offline CA gazetteer stays the primary resolver.
  The network fallback chain (Nominatim then Photon) becomes one call
  to Stadia's geocoding search
  (`https://api.stadiamaps.com/geocoding/v1/search`) with the existing
  California viewbox as `boundary.rect.*`, `size=1`, and the key from
  `STADIA_API_KEY`.
- Env unset: gazetteer only, then the existing model recalled
  coordinate fallback. That is the compliant default for self hosters
  and CI.
- The 1.1s Nominatim politeness throttle drops (paid service, no such
  policy); the in process cache stays. Module docstring rewritten.

### PR 4: docs and legal text

- `privacy.html`: name Stadia Maps as the processor for map tiles,
  routing, and geocoding requests (visitor IP and route or search
  coordinates reach them).
- `docs/deploy.md`: document `STADIA_API_KEY` mounting on both
  services and the dashboard domain allowlist step.
- Remove any remaining CARTO/OSRM/Nominatim references in docs.
- Record the WZDx feed license verification results (below) in the
  repo's data source docs if any need attribution changes.

## Error handling summary

Every Stadia touchpoint fails soft to today's degraded behavior: blank
map background for og images, dot only closures, gazetteer or model
coordinates for geocoding, and Leaflet's native broken tile handling in
the browser. No new hard failure modes.

## Testing

- TDD (red first) for: polyline6 decoder, roadsnap Valhalla adapter,
  snap loop conversion, staticmap URL builder, geocode.py Stadia call
  and env unset path. All network mocked via the existing
  httpx monkeypatch patterns in tests.
- Playwright locally (keyless localhost): map tiles render, a route
  computes on the planner, watch route preview draws.
- Prod verification after deploy: tiles 200 through the site, one real
  route round trip, one trip og image render, one MCP geocode call,
  zero CSP violations in the console, latency probe on /api/stats and
  /api/mapdata (the swap should not move them).

## Rollout

1. PRs 1 through 4, each merged only after CI SUCCESS with no pending
   checks.
2. Version bump (pyproject + server.json together), GitHub release.
3. Redeploy both services with `--update-secrets
   STADIA_API_KEY=stadiamaps-api:latest --project ca-roads-mcp`,
   demo with its standard flags (min 1, max 1, 2Gi, runtime SA).
4. Prod verification list above.
5. Burn in: check the Stadia usage dashboard for two days (no hard
   spending cap exists on their side).
6. Nic: subscribe to Starter before the trial ends (~2026-09-01).

## Compliance appendix (full re check, 2026-08-18)

- State DOT and federal feeds: compliant per the 2026-07-18 licensing
  audit; "Reported by X" labels satisfy attribution next to the data,
  verified present including 511.org and TravelMidwest (IDOT).
- 511 SF Bay obligations, not code: notify MTC within 30 days of
  public launch; they may charge with 90 days notice. Pre launch
  checklist item.
- WZDx feeds to verify license fields during PR 4: MD
  (filter.ritis.org), HI (ai.blyncsy.io), FL (one.network, published
  app key). All are FHWA registry entries, open by registry policy.
- NV DOT: terms unverified but the parser is dormant (no key, nothing
  served). No exposure.
- unpkg/jsdelivr/tailark hits in the tree are comment only source
  attributions inside vendored MIT files. No runtime CDN dependency.
- Fonts and Leaflet are vendored. OSM attribution remains on all maps
  after the swap (ODbL Produced Work, no share alike triggered).
- After this project the remaining commercial launch blockers are non
  code: MTC notification and a lawyer pass on the terms page.
