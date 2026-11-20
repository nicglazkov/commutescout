// A small model of the pipeline, read off the code, that the live figures run on.
//
// - TTLCache (ca_roads/cache.py): a copy younger than its refresh time is served as is;
//   at or past it, the old copy is still served and a refresh runs behind it, so a feed is
//   re-read at the first read after it turns stale, not on a fixed clock.
// - The publisher (ca_roads_demo/snapshot.py) reads every feed for live.json.gz every 30 s
//   and uploads only when the markers changed. signs.json.gz every 300 s, cameras every 3600 s.
// - The map (static/map-app.js) checks every 30 s with an ETag: 304 when nothing changed.
// The model assumes every new copy carries a change, and one map open.

export type Feed = { k: string; name: string; short: string; ttl: number; keep: number; f0: number; live: boolean };

export const FEEDS: Feed[] = [
  { k: "incident", name: "Highway patrol", short: "Patrol", ttl: 60, keep: 600, f0: -41, live: true },
  { k: "closure", name: "State DOT closures", short: "Closures", ttl: 300, keep: 1800, f0: -212, live: true },
  { k: "chain", name: "Other states' DOTs", short: "States", ttl: 180, keep: 1800, f0: -95, live: true },
  { k: "fire", name: "National fire service", short: "Fires", ttl: 300, keep: 3600, f0: -268, live: true },
  { k: "weather", name: "Signs and road weather", short: "Signs", ttl: 150, keep: 1800, f0: -64, live: false },
  { k: "neutral", name: "Camera lists", short: "Cameras", ttl: 150, keep: 21600, f0: -122, live: false },
];

export const BUILD = 30; // live.json.gz
export const CHECK_AT = 9; // the map's check lands this long after each build (any phase works)
export const LAND = 4; // a refetch takes a few seconds (all districts, conditional GETs)
export const LOOP = 1800;

export type Ev =
  | { t: number; type: "fetch"; i: number }
  | { t: number; type: "land"; i: number }
  | { t: number; type: "build"; changed: boolean }
  | { t: number; type: "check"; ok200: boolean };

// The whole loop is precomputed once: builds every 30 s, refetches when a copy has turned
// stale at a build, a new copy lands LAND s later, the next build uploads it, and the map's
// next check gets a 200.
function schedule() {
  const ev: Ev[] = [];
  const fetched = FEEDS.map((f) => f.f0);
  let pendingChange = false;
  let uploadedSinceCheck = false;
  for (let b = 0; b < LOOP; b += BUILD) {
    // landings from the previous build
    ev.push({ t: b, type: "build", changed: pendingChange });
    if (pendingChange) uploadedSinceCheck = true;
    pendingChange = false;
    FEEDS.forEach((f, i) => {
      if (b - fetched[i] >= f.ttl) {
        ev.push({ t: b, type: "fetch", i });
        fetched[i] = b + LAND;
        ev.push({ t: b + LAND, type: "land", i });
        if (f.live) pendingChange = true;
      }
    });
    ev.push({ t: b + CHECK_AT, type: "check", ok200: uploadedSinceCheck });
    uploadedSinceCheck = false;
  }
  return ev.sort((a, b) => a.t - b.t);
}
export const EVENTS = schedule();

export type State = {
  s: number;
  age: number[]; // seconds since each feed's copy landed
  fetching: (number | null)[]; // progress 0..1 of a refetch in flight
  build: { t: number; changed: boolean } | null; // the latest build
  check: { t: number; ok200: boolean } | null; // the latest map check
  last200: number | null;
};

export function stateAt(s: number): State {
  const landed = FEEDS.map((f) => f.f0);
  const fetching: (number | null)[] = FEEDS.map(() => null);
  let build: State["build"] = null;
  let check: State["check"] = null;
  let last200: number | null = null;
  for (const e of EVENTS) {
    if (e.t > s) break;
    if (e.type === "fetch") fetching[e.i] = Math.min(1, (s - e.t) / LAND);
    if (e.type === "land") {
      landed[e.i] = e.t;
      fetching[e.i] = null;
    }
    if (e.type === "build") build = { t: e.t, changed: e.changed };
    if (e.type === "check") {
      check = { t: e.t, ok200: e.ok200 };
      if (e.ok200) last200 = e.t;
    }
  }
  return { s, age: landed.map((l) => s - l), fetching, build, check, last200 };
}

// The clock the readouts show: an example morning starting 08:13:30.
export const T0 = 8 * 3600 + 13 * 60 + 30;
export function clock(s: number) {
  const c = Math.floor(T0 + s);
  const h = Math.floor(c / 3600);
  const m = Math.floor((c % 3600) / 60);
  const x = c % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}`;
}

// What the readout says: the newest thing that happened.
export function sayAt(st: State) {
  const { s, build, check } = st;
  const recentFetch = FEEDS.map((f, i) => ({ f, p: st.fetching[i] })).find((x) => x.p !== null);
  if (check && s - check.t < 6) return `${clock(check.t)} map check · ${check.ok200 ? "200, new markers" : "304, nothing new"}`;
  if (recentFetch) return `${clock(s)} ${recentFetch.f.short.toLowerCase()} copy stale · refetching`;
  if (build) return `${clock(build.t)} build · ${build.changed ? "changed, uploaded" : "unchanged, not uploaded"}`;
  return clock(s);
}

// The still frame (reduced motion, no JS): two seconds after a map check that got a 200,
// picked where the copies' ages are most spread out, so every gauge shows something.
export const STILL = (() => {
  let best = 41;
  let score = -1;
  for (const e of EVENTS) {
    if (e.type !== "check" || !e.ok200) continue;
    const st = stateAt(e.t + 2);
    const f = st.age.map((a, i) => Math.min(1, a / (2 * FEEDS[i].ttl)));
    const sc = Math.min(...f.slice(0, 5)) + f.reduce((x, y) => x + y, 0) / f.length;
    if (sc > score) {
      score = sc;
      best = e.t + 2;
    }
  }
  return best;
})();
