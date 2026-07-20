# State coverage matrix

What each live state actually has on the map, and why the gaps exist.
Updated 2026-07-20 (v2.32.0). See
[state-expansion-audit.md](state-expansion-audit.md) for states not yet
integrated.

Legend: Y = live on the map, "-" = the state's public feeds do not
offer it keylessly (reason noted), (wz) = closures come from the
state's WZDx roadwork feed.

| State | Incidents | Closures | Cameras | Signs | Road weather | Chains | Wildfires |
|---|---|---|---|---|---|---|---|
| California | Y | Y | Y | Y | Y | Y | Y |
| Maine | Y | Y | Y | Y | Y | n/a | Y* |
| New Hampshire | Y | Y | Y | Y | Y | n/a | Y* |
| Vermont | Y | Y | Y | Y | Y | n/a | Y* |
| Washington | Y | Y | Y | - (1) | Y | Y (passes) | Y* |
| Oregon | Y | Y | Y | - (2) | - (3) | - (4) | Y* |
| Ohio | Y | Y | Y | Y | Y | n/a | Y* |
| Maryland | Y | Y (wz) | - (5) | Y | Y | n/a | Y* |
| Illinois | Y | - (6) | Y | - (6) | - (6) | n/a | Y* |
| Alabama | - (7) | - (7) | Y | - (7) | - (7) | n/a | Y* |
| Missouri | - (8) | Y (wz) | - (8) | Y | - (8) | n/a | Y* |
| Iowa | - (9) | Y (wz) | - (9) | - (9) | - (9) | n/a | Y* |
| North Carolina | - (10) | Y (wz) | - (10) | - (10) | - (10) | n/a | Y* |
| Utah | - (11) | Y (wz) | - (11) | - (11) | - (11) | - (11) | Y* |
| Arizona | - (11) | Y (wz) | - (11) | - (11) | - (11) | n/a | Y* |
| Idaho | - (11) | Y (wz) | - (11) | - (11) | - (11) | - (11) | Y* |
| Wisconsin | - (11) | Y (wz) | Y** | - (11) | - (11) | n/a | Y* |
| New York | - (11) | Y (wz) | - (11) | - (11) | - (11) | n/a | Y* |
| Indiana | - (12) | Y (wz) | Y** | - (12) | - (12) | n/a | Y* |
| Minnesota | - (13) | Y (wz) | - (13) | - (13) | - (13) | n/a | Y* |
| Kansas | - (12) | Y (wz) | - (12) | - (12) | - (12) | n/a | Y* |
| New Jersey | - (14) | Y (wz) | - (14) | - (14) | - (14) | n/a | Y* |
| Kentucky | - (17) | Y (wz) | Y** | - (17) | - (17) | n/a | Y* |
| Oklahoma | - (17) | Y (wz) | - (17) | - (17) | - (17) | n/a | Y* |
| Hawaii | - (17) | Y (wz) | - (17) | - (17) | - (17) | n/a | Y* |
| Louisiana | - (17) | Y (wz) | - (17) | - (17) | - (17) | n/a | Y* |
| Delaware | Y | Y (wz) | - (18) | Y | Y | n/a | Y* |
| Michigan | Y | Y | - (19) | - (19) | - (19) | n/a | Y* |
| Tennessee | Y | Y | - (20) | - (20) | - (20) | n/a | Y* |
| Mississippi | Y | Y | - (21) | - (21) | - (21) | n/a | Y* |
| Texas (Austin metro) | - (16) | Y (wz) | - (16) | - (16) | - (16) | n/a | Y* |
| Nevada | traffic flow continuations only (15) | | | | | | Y* |

`Y*` Wildfires come from the national WFIGS interagency layer, so
every state has active-fire dots, and fires with a mapped perimeter in
the WFIGS year-to-date layer render their real burn footprint as a
polygon (nationwide since v2.32.0); fires without a perimeter record
stay dots and the popup says the shape is unknown. California
additionally merges CAL FIRE data.

`Y**` A subset of Wisconsin, Indiana, and Louisville-area Kentucky
cameras arrive via the TravelMidwest aggregation.

Live traffic overlay (TomTom tiles) and NWS weather alerts and USGS
quakes are nationwide by nature; the traffic overlay works over any
state.

## Why the gaps

1. **WA signs**: WSDOT's Traveler API has no DMS endpoint at all.
2. **OR signs**: TripCheck's DMS endpoint is an inventory (locations
   only) with no live message text; showing a sign without its message
   would be misleading.
3. **OR road weather**: no RWIS endpoint exists in the TripCheck API
   catalog we have access to.
4. **OR chains**: chain restrictions live inside TripCheck's
   road-and-weather report text; a parser for that prose is future
   work.
5. **MD cameras**: CHART publishes live *video* URLs, not still
   images; the popup UI is snapshot-based today.
6. **IL beyond incidents/cameras**: TravelMidwest's keyless CSVs cover
   incidents and cameras; signs exist but the DMS CSV carries
   Chicago-area gantries with formatting we have not mapped yet; winter
   road conditions are seasonal ArcGIS layers (future work).
7. **AL beyond cameras**: ALGO Traffic's other endpoints (incidents,
   signs) return 404/401 without credentials and are undocumented;
   ALDOT contact required.
8. **MO beyond signs/closures**: cameras are HLS streams with no still
   URL (snapshot-based popups), no incident or RWIS feed keyless.
9. **IA beyond closures**: the documented feeds behind Iowa 511
   (incidents, cameras with stills, DMS, RWIS) sit behind the
   credentialed CARS XML hub; the keyless path is WZDx only.
10. **NC beyond closures**: DriveNC's full API needs the key Nic
    holds, but its endpoint paths are only documented inside their SPA;
    discovery pending.
11. **Travel-IQ states (UT, AZ, ID, WI, NY)**: full incidents,
    cameras, signs, and weather exist behind the free developer key;
    requests are submitted and each state upgrades the moment its key
    arrives.
12. **IN, KS**: full data is in the credentialed Castle Rock CARS
    feeds (request-form access).
13. **MN**: metro-area IRIS XML dumps (incidents, signs, RWIS,
    cameras) are keyless and are the next planned upgrade; statewide
    needs the CARS credential.
14. **NJ**: events live in the TRANSCOM XCM exchange (free
    registration, commercial-friendly); cameras have no public feed.
15. **NV**: the nvroads key unlocks the full Travel-IQ dataset; the
    integration predates the multi-state layer and currently feeds the
    route-flow features. Uplift to full map coverage is queued.
16. **TX**: TxDOT's statewide feed terms prohibit third-party reuse,
    so only the City of Austin's CC0 open-data roadwork feed ships
    (Austin metro coverage).
17. **KY, OK, HI, LA**: the WZDx roadwork feed is the only thing
    these states publish keylessly (all CC0 per the federal registry;
    Oklahoma's access token is published verbatim in the registry
    entry). Kentucky's Louisville-area cameras already arrive through
    the TravelMidwest aggregation.
18. **DE cameras**: DelDOT publishes HLS video streams with no still
    URL; snapshot popups need stream support first.
19. **MI cameras, signs, weather**: MiDrive's camera list carries no
    still image URL and its sign list no message text (both need
    per-item detail calls); no RWIS feed exists.
20. **TN beyond events**: cameras, live sign text, and roadway weather
    sit behind SmartWay's embedded site key, which TDOT could rotate
    at any time; the keyless ArcGIS events layer ships instead. A
    stable key means a full upgrade.
21. **MS beyond alerts**: sign and camera endpoints exist on
    mdottraffic.com but are not yet resolved to stable URLs.
