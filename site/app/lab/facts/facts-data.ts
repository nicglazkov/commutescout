// Every figure the /lab/facts board shows, computed from the same sources
// the real pages use, so the board cannot show a number the code does not.
// Where a value lives only in Python (plugins, limits), it is restated here
// with the file and constant it comes from; the board prints that source
// under each option.
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";
import { STATE_COVERAGE, STATE_COVERAGE_UPDATED, type StateRow } from "@/lib/state-coverage";
import reference from "@/lib/api-reference.json";
import setup from "@/lib/mcp-clients.json";

export { AGENCY_FEED_COUNT, STATE_COUNT, STATE_COVERAGE_UPDATED };

// ---------- data sources ----------
export const LAYERS: { key: keyof StateRow; label: string; note?: string }[] = [
  { key: "incidents", label: "Crashes and incidents" },
  { key: "closures", label: "Closures and work zones" },
  { key: "cameras", label: "Cameras" },
  { key: "signs", label: "Message signs" },
  { key: "weather", label: "Road weather" },
  { key: "chains", label: "Chain controls", note: "seasonal" },
  { key: "wildfires", label: "Wildfires", note: "national" },
];
const has = (v: string) => v.startsWith("Y");
export const LAYER_COUNTS = LAYERS.map((l) => ({
  ...l,
  states: STATE_COVERAGE.filter((r) => has(r[l.key])).length,
}));
export const COVERED_STATES = STATE_COVERAGE.length;

// The five live layers a state's own feeds can publish (same rule as the
// coverage map figure and the data-sources page's FULL_STATES).
export const DEPTH_KEYS: (keyof StateRow)[] = ["incidents", "closures", "cameras", "signs", "weather"];
export const depthOf = (r: StateRow) => DEPTH_KEYS.filter((k) => has(r[k])).length;
export const DEPTH_BUCKETS = [5, 4, 3, 2, 1].map((d) => ({
  depth: d,
  states: STATE_COVERAGE.filter((r) => depthOf(r) === d).length,
}));
export const FULL_STATES = DEPTH_BUCKETS[0].states;

// Read cadences. Deepest state: the Refresh column of CA_FEEDS in
// lib/state-coverage.ts. Other states: src/ca_roads_demo/states.py TTL
// (180 s), CAM_TTL and WZDX_TTL (600 s). Map rebuild about every 30 s.
export const CADENCES = [
  { label: "Map rebuilt", every: "~30 s", s: 30 },
  { label: "Incidents, traffic speed", every: "1 min", s: 60 },
  { label: "Signs, cameras, road weather", every: "2.5 min", s: 150 },
  { label: "Most state event feeds", every: "3 min", s: 180 },
  { label: "Closures, chains, fires, alerts", every: "5 min", s: 300 },
  { label: "Work-zone files, camera lists", every: "10 min", s: 600 },
];
export const CADENCE_MAX_S = 600;

// ---------- API (REST and MCP share the tool list) ----------
type Tool = { name: string; path: string; poll_s: number; example: string; summary: string };
export const TOOLS = reference.tools as Tool[];
export const TOOL_COUNT = TOOLS.length;
export const API_ROOT = `${reference.base}${reference.prefix}`;
export const API_HOST = reference.base.replace(/^https?:\/\//, "");

// Same groups the MCP page and the server instructions use.
export const TOOL_GROUPS = [
  { title: "Trips", tools: ["plan_trip", "best_time_to_go", "find_place", "get_my_places"] },
  { title: "Around a place", tools: ["get_nearby_events", "get_weather", "get_traffic", "get_area_history", "get_coverage"] },
  {
    title: "Deepest state",
    tools: ["check_route", "check_region", "get_incidents", "get_lane_closures", "get_chain_controls", "get_wildfires", "get_cameras", "get_road_signs", "rank_routes"],
  },
];

// src/ca_roads/apikeys.py TIERS["free"]: daily 2000, burst 30,
// per_second 0.5 (= 30 a minute). Per account, shared by all its keys.
export const FREE = { daily: "2,000", perMinute: "30", burst: "30", keysPerAccount: "5" };

// ---------- MCP ----------
type Client = { id: string; name: string; key: boolean; steps: ({ lang: string; code: string } | { text: string })[] };
export const MCP_ENDPOINT = setup.endpoint;
export const CLIENTS = setup.clients as Client[];
export const READY_CLIENTS = CLIENTS.filter((c) => c.key && c.id !== "other");
export const firstCode = (id: string) => {
  const c = CLIENTS.find((x) => x.id === id);
  const s = c?.steps.find((x): x is { lang: string; code: string } => "code" in x);
  return s?.code ?? "";
};
export const MCP_PROMPTS = 3; // src/ca_roads_mcp/server.py: best_time, trip_check, road_trip_check

// ---------- plugins (src/ca_roads/flare.py) ----------
export const FLARE_PROTOCOL = "flare/1";
export const CAPABILITIES: [string, string, boolean][] = [
  ["alerts", "Serve alerts near a point", true],
  ["report", "Accept a new report from a user", false],
  ["confirm", "Accept a still there / not there vote", false],
  ["notify", "Mark alerts the apps may announce", false],
  ["snapshot", "Serve the whole list in one response", false],
];
export const KIND_GROUPS: [string, number][] = [
  ["Police", 3],
  ["Crash", 2],
  ["Hazard", 8],
  ["Weather", 5],
  ["Closures", 3],
  ["Traffic", 3],
  ["Chains", 2],
  ["Cameras", 3],
  ["Other", 2],
];
export const KIND_COUNT = KIND_GROUPS.reduce((n, [, c]) => n + c, 0); // 31 = len(flare.KINDS)
export const ENDPOINTS: [method: "GET" | "POST", path: string, needs: string][] = [
  ["GET", "/flare/v1/handshake", "required"],
  ["GET", "/flare/v1/alerts", "required"],
  ["POST", "/flare/v1/report", "report"],
  ["POST", "/flare/v1/confirm", "confirm"],
  ["GET", "/flare/v1/snapshot", "snapshot"],
];
// flare.py MAX_ALERTS, MAX_BYTES, MIN_REFRESH_S, MAX_RADIUS_M, SNAPSHOT_MAX_ALERTS
export const FLARE_CAPS = [
  { v: "500", l: "alerts per response" },
  { v: "1 MB", l: "largest alerts response" },
  { v: "15 s", l: "fastest refresh_s" },
  { v: "100 km", l: "largest radius asked" },
  { v: "20,000", l: "alerts in a snapshot" },
];
// flare.py tier_of: approved, unreviewed, private.
export const TIERS = [
  { name: "Private", who: "Added by URL on one device", alerts: "Only for you", tone: "muted" },
  { name: "Public, not reviewed", who: "Listed after the conformance check", alerts: "Alerts after you accept a notice", tone: "warn" },
  { name: "Approved", who: "Reviewed by CommuteScout", alerts: "May alert and, if you turn it on, speak", tone: "ok" },
];
