// Content pinned from docs/data-sources.md and docs/state-coverage.md.
// Rendered on site/app/data-sources/page.tsx and in the coverage map
// figure. The matrix is transcribed row for row; the notes and the feed
// table restate the docs in plain words for a first-time reader. The
// docs' per-gap reasons and parsing rules are deliberately not published
// on the site (owner review, 2026-11-19). Keep this file in lockstep with
// the source docs: when either changes, update the matching rows here in
// the same PR.

// docs/state-coverage.md's own "Updated" line.
export const STATE_COVERAGE_UPDATED = "2026-10-29 (v2.131.0)";

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
  { state: "Alabama", incidents: "Y", closures: "Y", cameras: "Y", signs: "Y", weather: "- (7)", chains: "n/a", wildfires: "Y*" },
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
  { state: "New York", incidents: "Y", closures: "Y", cameras: "- (11)", signs: "- (11)", weather: "- (11)", chains: "n/a", wildfires: "Y*" },
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

export const WILDFIRE_NOTE =
  "Wildfires come from the national interagency fire service, so every " +
  "state has them. When a fire's outline has been mapped, the map draws " +
  "its real shape. California also adds CAL FIRE's own reports.";

export const CAMERA_SUBSET_NOTE =
  "Some cameras in Wisconsin, Indiana and the Louisville area of Kentucky " +
  "come from a regional camera network those states share.";

export const OVERLAY_NOTE =
  "Live traffic speeds, National Weather Service alerts and earthquakes " +
  "cover every state.";

export type FeedRow = { source: string; data: string; refresh: string };

// docs/data-sources.md's "The feeds" table (California feeds), in plain words.
// refresh: how often CommuteScout reads the source (its cache time).
export const CA_FEEDS: FeedRow[] = [
  { source: "CHP live feed", data: "Highway patrol incidents (crashes, hazards, closures) as dispatchers log them, with each one's dispatch notes", refresh: "Every minute" },
  { source: "Caltrans LCS", data: "Lane and road closures in place right now, with what each means for through traffic", refresh: "Every 5 minutes" },
  { source: "Caltrans chain controls", data: "Chain requirements at mountain checkpoints", refresh: "Every 5 minutes" },
  { source: "WFIGS", data: "Active wildfires with name, size and containment, and their mapped outlines", refresh: "Every 5 minutes" },
  { source: "CAL FIRE", data: "CAL FIRE's own fire reports, for fires the national service has not listed yet", refresh: "Every 5 minutes" },
  { source: "Caltrans CMS", data: "What the electronic message signs say right now", refresh: "Every 2.5 minutes" },
  { source: "Caltrans CCTV", data: "Roadside cameras. Each image is checked for age before it is shown", refresh: "Every 2.5 minutes" },
  { source: "Caltrans RWIS", data: "Road weather stations: pavement temperature, wind gusts and visibility", refresh: "Every 2.5 minutes" },
  { source: "NWS alerts", data: "Winter storm, wind, flood, fog and fire weather warnings", refresh: "Every 5 minutes" },
  { source: "USGS quakes", data: "Earthquakes of magnitude 4.5 or more in the last 24 hours", refresh: "Every 5 minutes" },
  { source: "TomTom", data: "Current traffic speed compared with free-flow", refresh: "Every minute" },
  { source: "511 SF Bay", data: "Bay Area traffic events", refresh: "Every 3 minutes" },
  { source: "Nevada DOT", data: "Nevada events on routes that continue past the state line", refresh: "Every 3 minutes" },
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
