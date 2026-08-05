// Content pinned from docs/data-sources.md and docs/state-coverage.md.
// Rendered on site/app/data-sources/page.tsx. This file restyles those
// docs into a page; every string below is a fact transcribed from one of
// the two docs (or, for GAP_REASONS item 25, a fact with the raw email
// address removed - see the page's inline comment for why). Keep this
// file in lockstep with the source docs: when either changes, update the
// matching rows here in the same PR.

// docs/state-coverage.md's own "Updated" line.
export const STATE_COVERAGE_UPDATED = "2026-07-20 (v2.32.0)";

export type StateRow = {
  state: string;
  incidents: string;
  closures: string;
  cameras: string;
  signs: string;
  weather: string;
  chains: string;
  wildfires: string;
};

// docs/state-coverage.md's per-state matrix, row for row, cell for cell.
// Values keep the doc's exact notation ("Y", "Y (wz)", "Y (passes)", "Y*",
// "Y**", "- (n)", "n/a") so the page's cell renderer can interpret them
// the same way the doc's own legend does.
export const STATE_COVERAGE: StateRow[] = [
  { state: "California", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "Y", wildfires: "Y" },
  { state: "Maine", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "New Hampshire", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "Vermont", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "Washington", incidents: "Y", closures: "Y", cameras: "Y", signs: "- (1)", weather: "Y", chains: "Y (passes)", wildfires: "Y*" },
  { state: "Oregon", incidents: "Y", closures: "Y", cameras: "Y", signs: "- (2)", weather: "- (3)", chains: "- (4)", wildfires: "Y*" },
  { state: "Ohio", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "Maryland", incidents: "Y", closures: "Y (wz)", cameras: "- (5)", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "Illinois", incidents: "Y", closures: "- (6)", cameras: "Y", signs: "- (6)", weather: "- (6)", chains: "n/a", wildfires: "Y*" },
  { state: "Alabama", incidents: "- (7)", closures: "- (7)", cameras: "Y", signs: "- (7)", weather: "- (7)", chains: "n/a", wildfires: "Y*" },
  { state: "Missouri", incidents: "- (8)", closures: "Y (wz)", cameras: "- (8)", signs: "Y", weather: "- (8)", chains: "n/a", wildfires: "Y*" },
  { state: "Iowa", incidents: "- (9)", closures: "Y (wz)", cameras: "- (9)", signs: "- (9)", weather: "- (9)", chains: "n/a", wildfires: "Y*" },
  { state: "North Carolina", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "- (27)", chains: "n/a", wildfires: "Y*" },
  { state: "Utah", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "- (22)", wildfires: "Y*" },
  { state: "Arizona", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "Alaska", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "- (22)", wildfires: "Y*" },
  { state: "Colorado", incidents: "Y", closures: "Y", cameras: "- (23)", signs: "Y", weather: "Y", chains: "- (22)", wildfires: "Y*" },
  { state: "Florida", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "- (24)", chains: "n/a", wildfires: "Y*" },
  { state: "Virginia", incidents: "Y", closures: "Y (wz)", cameras: "- (25)", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "Idaho", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "- (22)", wildfires: "Y*" },
  { state: "Connecticut", incidents: "Y", closures: "Y", cameras: "- (26)", signs: "Y", weather: "- (26)", chains: "n/a", wildfires: "Y*" },
  { state: "Wisconsin", incidents: "- (11)", closures: "Y (wz)", cameras: "Y**", signs: "- (11)", weather: "- (11)", chains: "n/a", wildfires: "Y*" },
  { state: "New York", incidents: "- (11)", closures: "Y (wz)", cameras: "- (11)", signs: "- (11)", weather: "- (11)", chains: "n/a", wildfires: "Y*" },
  { state: "Indiana", incidents: "- (12)", closures: "Y (wz)", cameras: "Y**", signs: "- (12)", weather: "- (12)", chains: "n/a", wildfires: "Y*" },
  { state: "Minnesota", incidents: "- (13)", closures: "Y (wz)", cameras: "- (13)", signs: "- (13)", weather: "- (13)", chains: "n/a", wildfires: "Y*" },
  { state: "Kansas", incidents: "- (12)", closures: "Y (wz)", cameras: "- (12)", signs: "- (12)", weather: "- (12)", chains: "n/a", wildfires: "Y*" },
  { state: "New Jersey", incidents: "- (14)", closures: "Y (wz)", cameras: "- (14)", signs: "- (14)", weather: "- (14)", chains: "n/a", wildfires: "Y*" },
  { state: "Kentucky", incidents: "- (17)", closures: "Y (wz)", cameras: "Y**", signs: "- (17)", weather: "- (17)", chains: "n/a", wildfires: "Y*" },
  { state: "Oklahoma", incidents: "- (17)", closures: "Y (wz)", cameras: "- (17)", signs: "- (17)", weather: "- (17)", chains: "n/a", wildfires: "Y*" },
  { state: "Hawaii", incidents: "- (17)", closures: "Y (wz)", cameras: "- (17)", signs: "- (17)", weather: "- (17)", chains: "n/a", wildfires: "Y*" },
  { state: "Louisiana", incidents: "- (17)", closures: "Y (wz)", cameras: "- (17)", signs: "- (17)", weather: "- (17)", chains: "n/a", wildfires: "Y*" },
  { state: "Delaware", incidents: "Y", closures: "Y (wz)", cameras: "- (18)", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
  { state: "Michigan", incidents: "Y", closures: "Y", cameras: "Y", signs: "- (19)", weather: "- (19)", chains: "n/a", wildfires: "Y*" },
  { state: "Tennessee", incidents: "Y", closures: "Y", cameras: "- (20)", signs: "- (20)", weather: "- (20)", chains: "n/a", wildfires: "Y*" },
  { state: "Mississippi", incidents: "Y", closures: "Y", cameras: "- (21)", signs: "- (21)", weather: "- (21)", chains: "n/a", wildfires: "Y*" },
  { state: "Texas (Austin metro)", incidents: "- (16)", closures: "Y (wz)", cameras: "- (16)", signs: "- (16)", weather: "- (16)", chains: "n/a", wildfires: "Y*" },
  { state: "Nevada", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "Y", chains: "n/a", wildfires: "Y*" },
];

export type GapReason = { n: number; text: string };

// docs/state-coverage.md's numbered "Why the gaps" list, verbatim, with
// one exception: item 25's source text includes a support-program email
// address (511_videosubscription@iteris.com). The site's other pages
// deliberately carry no email address anywhere (see the comment in
// components/site-footer.tsx), so that address is left out here; every
// other word of the reason is unchanged.
export const GAP_REASONS: GapReason[] = [
  { n: 1, text: "WA signs: WSDOT's Traveler API has no DMS endpoint at all." },
  { n: 2, text: "OR signs: TripCheck's DMS endpoint is an inventory (locations only) with no live message text; showing a sign without its message would be misleading." },
  { n: 3, text: "OR road weather: no RWIS endpoint exists in the TripCheck API catalog we have access to." },
  { n: 4, text: "OR chains: chain restrictions live inside TripCheck's road-and-weather report text; a parser for that prose is future work." },
  { n: 5, text: "MD cameras: CHART publishes live video URLs, not still images; the popup UI is snapshot-based today." },
  { n: 6, text: "IL beyond incidents/cameras: TravelMidwest's keyless CSVs cover incidents and cameras; signs exist but the DMS CSV carries Chicago-area gantries with formatting we have not mapped yet; winter road conditions are seasonal ArcGIS layers (future work)." },
  { n: 7, text: "AL beyond cameras: ALGO Traffic's other endpoints (incidents, signs) return 404/401 without credentials and are undocumented; ALDOT contact required." },
  { n: 8, text: "MO beyond signs/closures: cameras are HLS streams with no still URL (snapshot-based popups), no incident or RWIS feed keyless." },
  { n: 9, text: "IA beyond closures: the documented feeds behind Iowa 511 (incidents, cameras with stills, DMS, RWIS) sit behind the credentialed CARS XML hub; the keyless path is WZDx only." },
  { n: 10, text: "Resolved in v2.38.0: DriveNC relaunched on Travel-IQ in May 2026 and the held key unlocks the standard endpoints." },
  { n: 11, text: "Travel-IQ states (WI, NY): full incidents, cameras, signs, and weather exist behind the free developer key; requests are submitted and each state upgrades the moment its key arrives (Utah, Arizona, Alaska, Idaho, and Connecticut upgraded this way)." },
  { n: 12, text: "IN, KS: full data is in the credentialed Castle Rock CARS feeds (request-form access)." },
  { n: 13, text: "MN: metro-area IRIS XML dumps (incidents, signs, RWIS, cameras) are keyless and are the next planned upgrade; statewide needs the CARS credential." },
  { n: 14, text: "NJ: events live in the TRANSCOM XCM exchange (free registration, commercial-friendly); cameras have no public feed." },
  { n: 15, text: "NV: fully covered since v2.38.0 (Travel-IQ key)." },
  { n: 16, text: "TX: TxDOT's statewide feed terms prohibit third-party reuse, so only the City of Austin's CC0 open-data roadwork feed ships (Austin metro coverage)." },
  { n: 17, text: "KY, OK, HI, LA: the WZDx roadwork feed is the only thing these states publish keylessly (all CC0 per the federal registry; Oklahoma's access token is published verbatim in the registry entry). Kentucky's Louisville-area cameras already arrive through the TravelMidwest aggregation." },
  { n: 18, text: "DE cameras: DelDOT publishes HLS video streams with no still URL; snapshot popups need stream support first." },
  { n: 19, text: "MI signs, weather: MiDrive's sign list carries no message text in any bulk feed; no RWIS feed exists. Cameras solved in v2.38.0 via the bulk list's embedded image URLs." },
  { n: 20, text: "TN beyond events: cameras, live sign text, and roadway weather sit behind SmartWay's embedded site key, which TDOT could rotate at any time; the keyless ArcGIS events layer ships instead. A stable key means a full upgrade." },
  { n: 21, text: "MS beyond alerts: sign and camera endpoints exist on mdottraffic.com but are not yet resolved to stable URLs." },
  { n: 22, text: "UT, AK, CO chains: chain and traction law state lives inside each API's road-conditions resource; a winter parser is queued for the season." },
  { n: 23, text: "CO cameras: CDOT's data API publishes no camera resource; their camera platform is separate." },
  { n: 24, text: "FL road weather: FDOT's keyless DIVAS layers carry events, cameras, and message boards but no RWIS; the FL511 API behind FDOT's data agreement would add it." },
  { n: 25, text: "VA cameras: SmarterRoads has no camera dataset; VDOT 511 video access is a separate free program (contact VDOT to enroll)." },
  { n: 26, text: "CT cameras and weather: CTDOT's developer API publishes no camera or weather-station resources (404 by design); their site's internal camera feed is unlicensed." },
  { n: 27, text: "NC road weather: DriveNC's API has no weather-station endpoint; its Snow and Ice road-conditions resource is seasonal and queued for winter." },
];

export const WILDFIRE_NOTE =
  "Wildfires come from the national WFIGS interagency layer, so every " +
  "state has active-fire dots, and fires with a mapped perimeter in the " +
  "WFIGS year-to-date layer render their real burn footprint as a " +
  "polygon (nationwide since v2.32.0); fires without a perimeter record " +
  "stay dots and the popup says the shape is unknown. California " +
  "additionally merges CAL FIRE data.";

export const CAMERA_SUBSET_NOTE =
  "A subset of Wisconsin, Indiana, and Louisville-area Kentucky cameras " +
  "arrive via the TravelMidwest aggregation.";

export const OVERLAY_NOTE =
  "Live traffic overlay (TomTom tiles) and NWS weather alerts and USGS " +
  "quakes are nationwide by nature; the traffic overlay works over any " +
  "state.";

export type FeedRow = { source: string; data: string; refresh: string };

// docs/data-sources.md's "The feeds" table (California feeds).
export const CA_FEEDS: FeedRow[] = [
  {
    source: "CHP live feed",
    data: "Statewide incidents (collisions, hazards, closures) as dispatchers log them, with travel direction parsed from the location text, plus the full shared dispatch timeline (comments and unit lifecycle, verbatim)",
    refresh: "1-minute cache; feed updates ~1/min",
  },
  {
    source: "Caltrans LCS",
    data: "Lane and road closures physically in place right now (CHP code 1097), classified by what they mean for through traffic",
    refresh: "5-minute cache",
  },
  {
    source: "Caltrans chain controls",
    data: "R-1/R-2/R-3 requirements at mountain checkpoints",
    refresh: "5-minute cache",
  },
  {
    source: "WFIGS",
    data: "Active wildfires (name, size, containment), flagged within ~10 miles of major highways; perimeter edges refine distances for big fires",
    refresh: "5-minute cache",
  },
  {
    source: "CAL FIRE",
    data: "CAL FIRE's own incident postings, merged into the wildfire layer for fires WFIGS does not list yet",
    refresh: "5-minute cache",
  },
  {
    source: "Caltrans CMS",
    data: "What changeable message signs display right now (blank signs filtered)",
    refresh: "2-minute cache",
  },
  {
    source: "Caltrans CCTV",
    data: "Roadside camera snapshots, image-verified live before return",
    refresh: "per query",
  },
  {
    source: "Caltrans RWIS",
    data: "Road-weather stations: pavement temperature, gusts, visibility on the passes",
    refresh: "5-minute cache",
  },
  {
    source: "NWS alerts",
    data: "Winter storm, wind, flood, fog, and fire-weather warnings along the route",
    refresh: "5-minute cache",
  },
  {
    source: "USGS quakes",
    data: "M4.5+ earthquakes near a corridor in the last 24 hours",
    refresh: "5-minute cache",
  },
  {
    source: "TomTom (optional key)",
    data: "Actual current speeds vs free-flow along the route",
    refresh: "1-minute cache",
  },
  {
    source: "511 SF Bay (optional key)",
    data: "Bay Area traffic events",
    refresh: "3-minute cache",
  },
  {
    source: "Nevada DOT (optional key)",
    data: "I-80, US-50, I-15 continuations past the state line",
    refresh: "3-minute cache",
  },
];

export type ClosureClass = { code: string; means: string; drive: string };

// docs/data-sources.md's closure taxonomy table.
export const CLOSURE_CLASSES: ClosureClass[] = [
  {
    code: "full-roadway",
    means: "The road itself is closed in that direction",
    drive: "No",
  },
  {
    code: "one-way-traffic",
    means: "Alternating single lane with flagging",
    drive: "Yes, with delays",
  },
  {
    code: "alternating-lanes / moving / traffic-break",
    means: "Rolling or brief work",
    drive: "Yes, minor delays",
  },
  {
    code: "lane",
    means: "Some lanes closed (\"2 of 4 lanes closed\")",
    drive: "Yes",
  },
  {
    code: "ramp",
    means: "One ramp or connector closed, road unaffected",
    drive: "Yes",
  },
];

// docs/data-sources.md's "Hard-won parsing rules" list, verbatim.
export const PARSING_RULES: string[] = [
  "CHP truncates its XML mid-record on busy days; the parser salvages every complete record instead of failing, and recently-seen incidents are carried forward briefly so they do not flap out of existence.",
  "Camera \"liveness\" is judged by image freshness (Last-Modified within 30 minutes), not byte size: night frames are tiny but live.",
  "A missing Caltrans district feed is treated as an empty district, not an error: one flaky district should not blank the state.",
  "Place names go through a real geocoder with an offline California gazetteer fallback, and when a street exists in several towns the tools say so and ask instead of guessing.",
];
