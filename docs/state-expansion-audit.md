# Multi-state expansion audit

Researched 2026-07-18 across all 50 states plus DC; statuses re-probed
live and updated 2026-07-20. Goal: rank every state by how turn-key
its road data is against the California baseline (live incidents,
closures/roadwork, cameras, message signs, road weather, chain
controls). Findings were verified by live endpoint fetches and the
USDOT WZDx feed registry where possible; anything marked UNVERIFIED
could not be confirmed from official sources and must be checked at
key signup before commercial use.

## TLDR status board (2026-07-20)

What is live on the map today, what one credential would unlock, and
what stays blocked. Per-category detail lives in
[state-coverage.md](state-coverage.md).

**Live now (35 jurisdictions, updated 2026-07-21).**
CA (full baseline), ME NH VT (full via NE Compass), WA OR OH UT AZ AK
CO (keyed, full), FL (keyless DIVAS + WZDx: events, 4,900 cameras,
signs), MD DE (multi-feed keyless), MI TN MS (MiDrive,
SmartWay events, MDOT Traffic), IL AL (cameras via
TravelMidwest/ALGO), MO (signs + WZDx), IA NC UT AZ ID WI NY IN MN KS
NJ KY OK HI LA (WZDx roadwork), TX-Austin (city CC0 feed), NV (route
flow). Wildfires, weather alerts, quakes, and the traffic overlay are
nationwide.

**One credential away (Nic: see the shopping list below).**
ID NY GA CT LA (Travel-IQ developer keys, one shared
client), VA (SmarterRoads
registration), NC (full DriveNC API), OH-WZDx (already keyed via
OHGO), MI-WZDx (form), MN IA IN KS MA NE (Castle Rock CARS credential
forms), ALDOT (contact for AL incidents), MT (contact MDT for the
road-weather API), WY (Trihydro SDX agreement).

**Reachable but unlicensed, holding.** The public map backends of
cotrip.org (CO), mass511.com (MA), 511.nebraska.gov (NE), 511mn.org
(MN), 511pa.com (PA), fl511.com (FL), ctroads.org (CT), and
mdottraffic.com sibling endpoints publish no data license; CO also has
a sanctioned keyed portal, which means the state channels developers
there on purpose. PA's icon feeds additionally carry no event text at
all. These stay out until terms are reviewed or keys arrive. TN's full
SmartWay API uses a site-embedded key that TDOT could rotate; only
their keyless ArcGIS events layer ships.

**Blocked.** AR (terms ban third-party apps), ND (non-commercial),
TX statewide (non-commercial mirror), SC WV NM WY RI (no usable public
feed found; details in the regional notes).

## Credentials shopping list for Nic

Exact steps, and the Secret Manager name to use so each state lights
up on deploy. All are free.

| Priority | State(s) | Where | Steps | Secret name |
|---|---|---|---|---|
| 1 | CO | DONE (key live 2026-07-21) | `cotrip-api-key` |
| 2 | FL | DONE keylessly (FDOT DIVAS + WZDx, 2026-07-21). Optional richer FL511 API: email James.Landini@dot.state.fl.us (no self-serve portal exists) | `fl511-api-key` (only if FDOT grants one) |
| 3 | GA | 511ga.org/my511/register | Same Travel-IQ flow | `ga511-api-key` |
| 4 | CT | ctroads.org/my511/register | Same Travel-IQ flow | `ct511-api-key` |
| 5 | LA | 511la.org/my511/register | Same Travel-IQ flow (upgrades the WZDx-only coverage) | `la511-api-key` |
| 6 | AK | 511.alaska.gov/my511/register | Same Travel-IQ flow | `ak511-api-key` |
| 7 | VA | smarterroads.vdot.virginia.gov | Register, accept the usage agreement, subscribe to cameras/incidents/closures/signs datasets | `smarterroads-token` |
| 8 | UT AZ ID NY | Already requested 2026-07-19 | Watch email for approvals | `ut511-api-key`, `az511-api-key`, `id511-api-key`, `ny511-api-key` |
| 9 | MI | michigan.gov/mdot ITS data page | Request the WZDx/RIDE data key (adds work zones beyond MiDrive) | `mi-ride-api-key` |
| 10 | AL | ALDOT / ALGO Traffic contact | Ask for API credentials for incidents and signs | `algo-api-key` |
| 11 | MT | MDT (app.mdt.mt.gov/atms Swagger contact) | Ask for the ATMS road-weather API key | `mdt-api-key` |
| 12 | MA NE MN IA IN KS | Castle Rock CARS request forms per state | Credential request form; slowest of the bunch | `{st}cars-user` / `{st}cars-pass` |

When any of these land in Secret Manager (project ca-roads-mcp),
say so and the matching adapter ships within a release.

Coverage notation: Y = available in a public machine-readable feed,
~ = partial or unverified, N = not available programmatically,
"-" = not applicable (no chain-control regime).

Tiers: A = one free API key (or no key) and go. B = feeds exist but
partial, fragmented, or gated behind request forms. C = scraping,
agreements, or FOIA territory.

## National summary

- **Tier A (or A-): 20 states.** OH, ME, NH, VT, MD, DE, NY, VA, NC,
  GA, OR, UT, WA, AZ, IA, MO, ID, IL, WI, LA (plus NV, already
  integrated, and PA at A-).
- **The single biggest shortcut: Arcadis Travel-IQ.** The exact API
  CommuteScout already runs for Nevada (`/api/v2/get/{resource}?key=`,
  free key, 10 calls/60s, docs at `{site}/developers/doc`) is shared by
  **UT, AZ, ID, AK, WI, LA** in the west and **NY, CT, GA, NC** in the
  east. One client plus per-state hostname and key unlocks about ten
  states.
- **Castle Rock CARS** is the second family: CO, MN, KS, NE, IN, MA
  (plus Iowa's 511 pipeline). One FEU-XML/CIFS parser and one
  credential-request process.
- **WZDx (Work Zone Data Exchange)** is the universal closures layer:
  roughly 30 of 51 jurisdictions publish feeds, most keyless and CC0.
  One WZDx 4.x parser gives day-one roadwork coverage across more than
  half the country before any full integration.
- **Nobody replicates CHP's machine-readable CAD.** Closest analogs,
  all scrape-only: Montana Highway Patrol (true live CAD viewer,
  HTML), Florida Highway Patrol (live CAD viewer, HTML), Missouri
  MSHP (auto-posted crash log), MN/KS crash-log portals, Honolulu PD
  (15-min HTML). Everywhere else, police incidents arrive via DOT
  feeds.
- **License landmines** (technically easy, legally blocked without a
  DOT letter): Arkansas (ToU bans third-party apps), North Dakota
  (non-commercial without written consent), Texas (public ArcGIS
  mirror is non-commercial only).
- **Iteris-run 511 sites are a strong negative predictor**: MT, SD,
  SC, WV publish no developer feeds at all.

### Top 10 easiest states nationally

1. **Utah**: hostname+key swap on the existing Nevada client; adds
   snowplow AVL and mountain-pass data; CC0 WZDx.
2. **Ohio**: one instant free key, all six data classes, data declared
   public domain, generous rate limit.
3. **Arizona**: same client as Nevada; closes the CA/NV/AZ tri-state.
4. **Oregon**: the only other state matching all six CA data types
   including explicit tire-chain restrictions, one free keyed API.
5. **Maine + New Hampshire + Vermont**: three states, one keyless
   endpoint, CA-grade coverage including RWIS.
6. **Washington**: instant email signup; mountain-pass traction
   restrictions are the best chain-control analog; no DMS feed.
7. **Iowa**: keyless CC0/CC-BY ArcGIS REST for everything; the
   cleanest open-data license in the country.
8. **Maryland**: keyless CHART JSON covering all five eastern classes
   plus open WZDx; confirm commercial terms.
9. **New York**: fully documented API with the clearest written
   commercial-use license in the east ("powered by 511NY" attribution).
10. **Missouri**: wide-open keyless JSON (WZDx portion CC0), just
    undocumented; includes DMS with sign images and HLS cameras.

---

## West + Central (25 states)

| State | Tier | Inc | Clo | Cam | Sig | Wx | Chn | API + key + license | Vendor |
|---|---|---|---|---|---|---|---|---|---|
| OR | A | Y | Y | Y | Y | Y | Y | TripCheck Data API; free self-serve key (Azure portal), click-through ToU | ODOT in-house |
| UT | A | Y | Y | Y | Y | Y | ~ | UDOT Traffic API; free key, 10 calls/60s; WZDx is CC0 | Arcadis Travel-IQ |
| WA | A | Y | Y | Y | N | Y | Y | WSDOT Traveler API; email for instant access code; formal license UNVERIFIED | WSDOT in-house |
| AZ | A- | Y | Y | ~ | Y | Y | - | AZ511 API; free key, 10/60s; keyless WZDx | Arcadis Travel-IQ |
| NV | A (done) | Y | Y | Y | Y | Y | ~ | nvroads API (integrated); free key | Arcadis Travel-IQ |
| IA | A | Y | Y | Y | Y | Y | - | ArcGIS REST, keyless, CC0/CC-BY; plus CARS XML (credentialed) and keyless WZDx | Castle Rock 511 / Q-Free ATMS |
| MO | A | Y | Y | Y | Y | ~ | - | Keyless undocumented JSON feeds; WZDx CC0; other terms unstated | MoDOT in-house |
| ID | A | Y | Y | Y | Y | Y | - | Idaho 511 API; free key, 10/60s; keyless WZDx | Arcadis Travel-IQ |
| IL | A- | Y | Y | Y | Y | ~ | - | TravelMidwest CSVs keyless + IDOT ArcGIS; poll caps + attribution; revenue redistribution needs agreement | UIC AI Lab (GTIS) + Esri |
| WI | A- | Y | Y | Y | Y | N | - | 511WI API; free but human-approved key, 10/60s; WZDx keyless CC0 | Arcadis Travel-IQ |
| LA | A- | Y | Y | ~ | Y | N | - | 511LA API; free key, 10/60s; cameras HLS-only | Arcadis Travel-IQ |
| AK | B+ | Y | Y | Y | Y | Y | - | Alaska 511 API; free key, 10/60s; WZDx endpoint live but empty | Arcadis Travel-IQ |
| NE | B+ | Y | Y | ~ | ~ | Y | - | CARS FEU/CIFS XML; request-form credentials; terms in access agreement | Castle Rock CARS |
| MN | B+ | Y | Y | ~ | Y | Y | - | Keyless IRIS XML (metro) + WZDx CC0; statewide via credentialed CARS XML | Castle Rock CARS + IRIS |
| ND | A-/B | Y | Y | Y | N | Y | - | Keyless documented GeoJSON, but NON-COMMERCIAL license; written consent needed | NDDOT in-house |
| CO | B | Y | Y | ~ | ~ | Y | ~ | COtrip data feed, self-serve key (manage-api.cotrip.org); thin public docs | Castle Rock ITS |
| KS | B | Y | Y | ~ | ~ | ~ | - | CARS FEU XML via email to KDOT; WZDx keyless CC0 | Castle Rock CARS |
| WY | B | ~ | Y | N | N | ~ | ~ | Trihydro SDX (register + agreement, TIM format); no simple REST 511 API | WYDOT + Trihydro SDX |
| OK | B | N | Y | N | N | N | - | WZDx workzones/closures/detours public (CC0); everything else auth-locked | ODOT + OU ITS |
| TX | B-C | ~ | ~ | N | N | ~ | - | DriveTexas WZDx key by private request; ArcGIS mirror non-commercial only | TxDOT in-house |
| MT | C+ | N | N | ~ | N | ~ | N | No public feed; scrapable cameras + live MHP CAD; undocumented ATMS Swagger | Iteris |
| NM | C | N | N | N | N | N | - | No public API; feeds exist B2B-only (contact NMDOT ITS) | Real Time Solutions |
| AR | C | Y* | Y* | Y* | ~* | N | - | *Open S3 GeoJSON, but ToU explicitly prohibits third-party app use | ARDOT in-house |
| SD | C | N | N | N | N | N | - | No feed program at all; negotiate with SDDOT/Iteris or scrape | Iteris |
| HI | C | N | ~ | N | N | N | - | No 511, no API; Blyncsy WZDx (ML-inferred); GoAkamai SPA scraping | ICx Transportation Group |

### West + Central notes

- **WA (A)**: WSDOT Traveler Information API (wsdot.wa.gov/traffic/api).
  Email for instant access code; 14 REST services incl. Highway Alerts,
  Cameras, Weather Stations, Commercial Vehicle Restrictions, and
  Mountain Pass Conditions with explicit RestrictionOne/Two traction
  fields, the best chain-control analog outside OR. Keyless WZDx v4.2
  at wzdx.wsdot.wa.gov/api/v4/WorkZoneFeed. Gap: no DMS endpoint.
- **OR (A)**: TripCheck Data API (tripcheck.com/Pages/API, portal
  apiportal.odot.state.or.us). Free self-serve; JSON/XML. The one
  state with all six CA types: CCTV stills, DMS inventory+status,
  30-second incidents, RWIS, and road/weather reports that explicitly
  include tire-chain restrictions. WZDx inside the same API.
- **NV (done)**: nvroads.com /api/v2/get/* (Travel-IQ). Reference
  implementation for the sibling states. NHP incident page is web-only.
  Chain-control API field UNVERIFIED; confirm in the existing
  integration.
- **UT (A)**: udottraffic.utah.gov/developers/doc (same API shape as
  nvroads). Adds snowplow AVL and a Mountain Passes endpoint with
  per-pass RWIS; explicit chain-law field UNVERIFIED. Keyless CC0 WZDx:
  udottraffic.utah.gov/wzdx/udot/v40/data.
- **AZ (A-)**: az511.com/developers/doc (Travel-IQ). No road-conditions
  endpoint documented; camera Views[].Url points at a page, direct
  media URL UNVERIFIED. Live keyless statewide WZDx at
  az511.com/api/wzdx.
- **ID (A)**: 511.idaho.gov/developers/doc (Travel-IQ). Events,
  Cameras, Message Signs, Road Conditions, Weather Stations, Mountain
  Passes, truck Restrictions. Keyless WZDx at 511.idaho.gov/api/wzdx.
- **MT (C+)**: no public feed; 511mt.net (Iteris) has no developer
  page. Scrapable direct-JPEG cameras (app.mdt.mt.gov/atms/public/cameras);
  undocumented Swagger at app.mdt.mt.gov/atms/api. Rare find: Montana
  Highway Patrol live public CAD at
  app.doj.mt.gov/apps/SmartWebClient/CADView.aspx (HTML scrape), the
  only true CHP-style live CAD in the west.
- **WY (B)**: the I-80 closure/wind/VSL data flows through Trihydro
  SDX (sdx.trihydro.com): registration + agreement, TIM/WZDx formats,
  cost UNVERIFIED. wyoroad.info has no developer page; chain-law
  status has no machine feed found.
- **CO (B)**: self-serve key at manage-api.cotrip.org, feeds at
  data.cotrip.org/api/v1/* (GeoJSON). Two registry WZDx feeds (keyed).
  DMS/chain-law fields UNVERIFIED; expect schema discovery after
  signup. Castle Rock, so a different adapter than Travel-IQ.
- **NM (C)**: nmroads.com is a custom build with no developer portal;
  feeds exist B2B-only. Path: email NMDOT ITS Bureau.
- **AK (B+)**: 511.alaska.gov/developers/doc (Travel-IQ). Events,
  workzones, cameras, signs, weather stations + roadweather.alaska.gov
  RWIS.
- **HI (C)**: no 511, no API. GoAkamai is a SPA; Blyncsy ML-inferred
  WZDx; Honolulu PD posts dispatch calls as HTML.
- **ND (A- technical, B legal)**: documented keyless GeoJSON at
  travelfiles.dot.nd.gov/geojson_nc/ (alerts, cameras with image URLs,
  roads, workzones, RWIS, load restrictions). Blocker: license is
  non-commercial; commercial use needs express written NDDOT consent,
  and polling must be 5 minutes or slower. No DMS feed.
- **SD (C)**: sd511.org exposes nothing. Scrape or negotiate.
- **NE (B+)**: Castle Rock CARS XML via ne.carsprogram.org/hub;
  credentials via castlerockits.com/xml-data-feeds request form.
  Incidents/construction/closures/truck restrictions/winter;
  cameras/DMS in-feed UNVERIFIED.
- **KS (B)**: same CARS stack (ks.carsprogram.org/hub), credentials by
  emailing KDOT. Keyless CC0 WZDx at
  kscars.kandrive.gov/carsapi_v1/api/wzdx. KHP posts crash logs, not
  live CAD.
- **OK (B)**: public CC0 WZDx trio at
  oktraffic.org/api/Geojsons/{workzones|closures|detours} with an
  openly published token; incidents/cameras/DMS return 401 and need an
  ODOT arrangement.
- **TX (B-C)**: DriveTexas WZDx (api.drivetexas.org/api/conditions.wzdx.geojson)
  is key-gated with no self-serve signup; the public ArcGIS mirror is
  explicitly non-commercial. Biggest market, weakest turn-key path;
  needs a TxDOT relationship.
- **MN (B+)**: keyless IRIS XML dumps (metro incidents, DMS, RWIS,
  camera config) at data.dot.state.mn.us/iris_xml/ with constructable
  JPEG URLs; keyless CC0 WZDx at mn.carsprogram.org; statewide events
  need the credentialed CARS feed (revocable at will).
- **IA (A)**: documented at iowadot.gov/travel-tools/iowa-511/511-data-feeds.
  Anonymous ArcGIS REST (incidents, cameras with ImageURL+VideoURL,
  DMS, RWIS, road conditions, 2-min plow AVL) under CC0/CC-BY.
- **MO (A)**: keyless JSON under traveler.modot.org/timconfig/feed/desktop/
  (mo_wzdx.json CC0, DMS with sign images, HLS cameras, winter
  conditions) plus ArcGIS truck layers. MSHP auto-posts injury/fatal
  crashes (scrapeable). Non-WZDx terms unstated.
- **AR (C, legal-gated)**: technically open S3 GeoJSON
  (layers.idrivearkansas.com) and a public DMS FeatureServer, but the
  IDrive Arkansas AUP explicitly denies authorization to third-party
  app developers. Requires written ARDOT permission.
- **LA (A-)**: 511la.org/developers/doc (Travel-IQ). Incidents,
  closures with IsFullClosure/detours, DMS, HLS-only cameras; no RWIS.
- **WI (A-)**: 511wi.gov/developers/doc (Travel-IQ): events, cameras
  with image and video URLs, DMS, winter road conditions. Key is
  human-approved with a use-case review. RWIS locked behind
  UW-Madison WisTransPortal.
- **IL (A-)**: no 511. Zero-credential CSVs from TravelMidwest
  (travelmidwest.com/lmiga/*.csv, docs wiki.travelmidwest.com) plus
  keyless ArcGIS winter/construction layers. Poll caps + attribution;
  revenue-generating redistribution needs a signed agreement.

---

## East + South (25 jurisdictions)

No eastern state has a chain-control analog; winter/snow-ice road
condition feeds are the closest equivalent (NY, PA, ME/NH/VT, NC, KY).

| State | Tier | Inc | Clo | Cam | Sig | Wx | API + key + license | Vendor |
|---|---|---|---|---|---|---|---|---|
| OH | A | Y | Y | Y | Y | Y | OHGO Public API, free self-serve key, data declared public domain | ODOT in-house |
| ME | A | Y | Y | Y | Y | Y | NE Compass C2C XML, no key at all, click-through terms | NE Compass ATMS |
| NH | A | Y | Y | Y | Y | Y | Same NE Compass endpoint, networks=NewHampshire | Same |
| VT | A | Y | Y | Y | Y | Y | Same NE Compass endpoint, networks=Vermont | Same |
| MD | A | Y | Y | Y | Y | Y | CHART JSON/XML feeds, no key; formal license unposted (UNVERIFIED) | MDOT CHART in-house |
| DE | A | Y | Y | Y | Y | Y | Keyless JSON (tmc.deldot.gov) + ArcGIS Gateway; license UNVERIFIED | DelDOT in-house |
| NY | A | Y | Y | Y | Y | Y | 511NY REST, free key, 10 calls/min; commercial use + attribution explicitly OK | Arcadis Travel-IQ |
| VA | A | Y | Y | ~ | Y | Y | SmarterRoads portal, free token per-dataset, data-sharing agreement | Iteris |
| NC | A | Y | Y | Y | Y | ~ | DriveNC API, free key, 10 calls/min; WZDx keyless | Travel-IQ pattern |
| GA | A | Y | Y | Y | Y | N | 511GA REST, free key, 10 calls/min; terms UNVERIFIED | Arcadis Travel-IQ |
| PA | A- | Y | Y | ~ | ~ | Y | RCRS Event API, free via request form, Basic auth, attribution required | PennDOT in-house |
| CT | A-/B | Y | Y | N | Y | N | CTroads REST, free key, 10 calls/min; commercial terms UNVERIFIED | Arcadis IBI |
| MA | B | Y | Y | ~ | Y | N | 4 separate channels: event XML, GoTime, CWZ key, TrafficLand cams | Castle Rock (Mass511) |
| IN | B | Y | Y | Y | N | Y | Open keyless WZDx today; CARS FEU XML via request form | Castle Rock CARS |
| MI | B | ~ | ~ | ~ | ~ | ~ | MDOT RIDE, free but MiLogin-for-Business signup; catalog gated | MDOT in-house |
| FL | B | Y | Y | ~ | ~ | N | Keyless WZDx (one.network); full feed = FDOT agreement; FHP live CAD (HTML) | SunGuide + Arcadis web |
| AL | B | ~ | ~ | Y | ~ | N | api.algotraffic.com open JSON, no key, no docs, no stated terms | Univ. of Alabama CAPS |
| KY | B | Y | Y | N | N | ~ | Keyless WZDx GeoJSON + KYTC ArcGIS; GoKY backend UNVERIFIED | KYTC in-house |
| TN | B | Y | Y | N | N | N | TDOT ArcGIS FeatureServer (events, keyless); cams/DMS site-only | In-house |
| NJ | B | Y | Y | N | N | N | TRANSCOM XCM (free reg, commercial OK) + NJIT keyless WZDx; no 511NJ API | TRANSCOM |
| MS | C | N | N | N | N | N | None; the site's "API" link is a dead anchor; scrape or negotiate | UNVERIFIED |
| SC | C | N | N | N | N | N | None; no developer module; SCHP webCAD confirmed dead | Iteris |
| WV | C | N | N | N | N | N | None; static GIS only | UNVERIFIED |
| RI | C | ~ | ~ | ~ | N | N | None; no 511 program; scrapeable JPEGs, HTML advisories | In-house |
| DC | C | N | N | ~ | N | N | None; video via TrafficLand (paid); RITIS closed to commercial | n/a |

### East + South notes

- **OH (A)**: publicapi.ohgo.com (Swagger docs). Free instant key,
  ~25 req/s. Cameras, construction, dangerous slowdowns, digital
  signs, incidents, delays, truck parking, weather sensors, work zones
  + WZDx 4.2. Terms declare data public domain: the most
  commercial-friendly in the country.
- **ME/NH/VT (A)**: one tri-state system,
  nec-por.ne-compass.com/DeveloperPortal. Zero-auth C2C XML:
  .../NEC.XmlDataPortal/api/c2c?networks={state}&dataTypes={incidentData|laneClosureData|cctvSnapshotData|dmsData|essData}
  (verified live, no key). TMDD-style XML is the only friction. Read
  /Home/Terms before launch.
- **MD (A)**: chart.maryland.gov/DataFeeds/GetDataFeeds: keyless
  JSON/XML for incidents, closures, cameras (live video, no stills),
  DMS, RWIS, speed sensors + keyless WZDx. Formal license not posted;
  confirm commercial terms with CHART.
- **DE (A)**: keyless JSON, e.g. tmc.deldot.gov/json/videocamera.json
  (360 cams with HLS). DelDOT Gateway ArcGIS covers the layers.
  Keyless WZDx via wzdx.e-dot.com. Tiny geography, essentially free.
- **NY (A)**: 511ny.org/developers/help: GetEvents, GetAlerts,
  GetCameras, GetMessageSigns, GetWinterRoadConditions. Free key; 10
  calls/60s (cache hard). Terms explicitly permit free commercial use
  with "powered by 511NY" attribution: the clearest license in the
  east. Keyless WZDx at 511ny.org/api/wzdx.
- **VA (A)**: SmarterRoads (smarterroads.vdot.virginia.gov): free
  account + data-sharing agreement, then per-dataset token. ~22
  datasets incl. truck restrictions and weather; the CA-like breadth
  leader. Camera dataset UNVERIFIED.
- **NC (A)**: drivenc.gov/developers/doc: events, cameras, message
  signs, snow/ice conditions, alerts; free key. Keyless WZDx 4.2 at
  drivenc.gov/api/wzdx.
- **GA (A)**: 511ga.org/developers/doc: cameras, signs, events,
  alerts; free key. No RWIS, no WZDx.
- **PA (A-)**: RCRS Event API (JSON, Basic auth) via PennDOT's data
  feed request form; free, attribution required. Camera video needs a
  separate signed agreement. Statewide WZDx not live.
- **CT (A-/B)**: ctroads.org/developers/doc: GetEvents,
  GetMessageSigns, GetAlerts; cameras/weather on the site but not in
  the API.
- **MA (B)**: real data, fragmented: event XML (arranged with
  MassDOT), GoTime travel times, Connected Work Zones keyed feed,
  cameras only via TrafficLand at 1 frame/120s.
- **IN (B)**: start with keyless WZDx
  (in.carsprogram.org/carsapi_v1/api/wzdx); the full CARS FEU XML
  (incidents, maintenance, weather, truck restrictions, CCTV) comes
  via Castle Rock's request form.
- **MI (B)**: MDOT RIDE requires MiLogin-for-Business registration
  before the dataset catalog is even visible; only the WZDx dataset is
  confirmed. Start registration early; slowest onboarding in the east.
- **FL (B)**: no self-serve FL511 developer portal; the full SunGuide
  feed needs an FDOT agreement (contract being re-bid in 2026). Turn
  key today: keyless WZDx via one.network, and the live FHP CAD viewer
  (trafficincidents.flhsmv.gov, ~5-min refresh, HTML scrape), the only
  CHP analog in the east.
- **AL (B)**: api.algotraffic.com/v4.0/cameras is open JSON with HLS
  streams and snapshots (verified); incident/DMS endpoints
  undocumented. No published terms; contact the Univ. of Alabama CAPS
  before commercial use.
- **KY (B)**: keyless WZDx 4.1 GeoJSON + KYTC ArcGIS layers. GoKY
  backend UNVERIFIED. Note: data.transportation.ky.gov does not exist
  (dead lead).
- **TN (B)**: TDOT ArcGIS REST is open and keyless
  (tspatial.tdot.tn.gov Smartway_Events). Cameras and DMS are
  site-only.
- **NJ (B)**: no documented 511NJ API. The real channel is TRANSCOM
  XCM Data Exchange (data1.xcmdata.org): free registration explicitly
  open to commercial vendors; carries 14 NY/NJ/CT agency event feeds.
  Keyless WZDx via NJIT. Cameras = scraping.
- **MS / SC / WV / RI / DC (C)**: no developer feeds. SC's highway
  patrol webCAD is confirmed discontinued. DC incidents live inside
  the closed RITIS ecosystem (explicitly closed to commercial use);
  serve DC via MD/VA overlap. RI has no 511 program at all.

---

## Suggested integration order

1. **Travel-IQ fleet, wave 1** (reuse the Nevada client): UT, AZ, ID.
   Three states for near-zero marginal code.
2. **OR + WA**: the chain-control states; two bespoke but excellent
   APIs. With CA/NV/UT/AZ/ID this completes a contiguous western
   block.
3. **OH + IA + MO**: the open-data midwest anchors.
4. **Travel-IQ fleet, wave 2**: NY, GA, NC (+ CT), plus ME/NH/VT via
   one NE Compass integration and MD/DE keyless feeds: the eastern
   seaboard largely falls out of two adapters.
5. **WZDx everywhere**: one parser lights up roadwork/closures in ~30
   jurisdictions, including states awaiting full integration.
6. **Deliberately defer**: TX/NM/AR/ND (agreements or non-commercial
   terms), MT/SD/WY/HI/MS/SC/WV/RI/DC (scraping or partnerships).

## Standing caveats

- Every state marked UNVERIFIED needs its terms read at key signup;
  several Travel-IQ signups may carry click-through terms not visible
  publicly.
- Rate limits are low across the Travel-IQ fleet (10 calls/60s):
  server-side caching per state is mandatory, same as the current
  feed-cache architecture.
- Items to close with real keys: AZ camera media URLs, chain-law
  fields in NV/UT/CO feeds, COtrip endpoint catalog, Travel-IQ signup
  commercial-use language, Trihydro SDX pricing, MD/DE/GA/CT formal
  license terms.
