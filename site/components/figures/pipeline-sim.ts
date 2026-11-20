// The model the "From agency feed to your map" figure runs on, read off the backend code.
//
// - Each source sits in a TTLCache (src/ca_roads/cache.py). A copy younger than its refresh
//   time is served as is. At or past it, the old copy is served once more and a new one is
//   fetched behind it, so a source is re-read at the first read after its copy turns due, not on
//   a fixed clock. The copy's age counts from when the fetch finished.
// - Refresh times: highway patrol 60 s (feeds/chp.py), closures and chain controls 300 s
//   (feeds/lcs.py, feeds/chains.py), other states' feeds 180 s (ca_roads_demo/states.py TTL),
//   wildfires 300 s (feeds/wildfire.py, feeds/calfire.py).
// - The publisher (ca_roads_demo/snapshot.py BUNDLES) builds live.json.gz every 30 s, reading
//   every one of those sources. It uploads when the markers changed, or when the last upload is
//   60 s old (max_stale) so the file's "as of" time stays current; otherwise it skips the upload.
// - The map (static/map-app.js) fetches the file every 30 s with cache: "no-cache", so it
//   downloads only a file that changed since its last check.
//
// Assumptions, so the loop is concrete: the publisher is the only reader (API and assistant
// reads can refresh a copy sooner), every new copy carries a change, a fetch takes LAND s, one
// map is open and its check lands CHECK_AT s after each build. The edge cache in front of the
// file is left out: it can hold an upload back by up to one check.
// Signs and road weather (their own file every 300 s) and camera lists (every 3600 s) follow the
// same rules on slower clocks and are named in the caption instead of drawn.

export type Feed = { k: string; name: string; what: string; every: string; ttl: number; f0: number };

export const FEEDS: Feed[] = [
  { k: "patrol", name: "Highway patrol", what: "crashes and incidents", every: "1 min", ttl: 60, f0: -50 },
  { k: "dot", name: "Road department", what: "closures, chain controls", every: "5 min", ttl: 300, f0: -200 },
  { k: "states", name: "State DOT feeds", what: "incidents, roadwork", every: "3 min", ttl: 180, f0: -100 },
  { k: "fire", name: "Fire services", what: "active wildfires", every: "5 min", ttl: 300, f0: -290 },
];

export const BUILD = 30;
export const MAX_STALE = 60;
export const CHECK_AT = 20;
export const LAND = 4;
// how long the drawing takes to carry the copies into the file, and the file to the map
export const CARRY = 4;
export const HORIZON = 6 * 3600; // long enough that nobody sees it wrap

export type Ev =
  | { t: number; type: "fetch"; i: number }
  | { t: number; type: "land"; i: number }
  | { t: number; type: "build"; upload: "changed" | "refresh" | "none" }
  | { t: number; type: "check"; got: boolean };

function schedule(): Ev[] {
  const ev: Ev[] = [];
  const landed = FEEDS.map((f) => f.f0);
  let changedSince = false; // a new copy landed since the last build
  let lastUpload = -BUILD;
  let uploadedSinceCheck = false;
  for (let b = 0; b < HORIZON; b += BUILD) {
    let upload: "changed" | "refresh" | "none" = "none";
    if (changedSince) upload = "changed";
    else if (b - lastUpload >= MAX_STALE) upload = "refresh";
    if (upload !== "none") {
      lastUpload = b;
      uploadedSinceCheck = true;
    }
    changedSince = false;
    ev.push({ t: b, type: "build", upload });
    // the build read every copy; a due one is fetched behind it
    FEEDS.forEach((f, i) => {
      if (b - landed[i] >= f.ttl) {
        ev.push({ t: b, type: "fetch", i });
        ev.push({ t: b + LAND, type: "land", i });
        landed[i] = b + LAND;
        changedSince = true;
      }
    });
    ev.push({ t: b + CHECK_AT, type: "check", got: uploadedSinceCheck });
    uploadedSinceCheck = false;
  }
  return ev.sort((a, b) => a.t - b.t);
}
export const EVENTS = schedule();

export type State = {
  s: number;
  age: number[]; // seconds since each copy landed
  fetching: (number | null)[]; // 0..1 while a new copy is on its way
  build: Extract<Ev, { type: "build" }> | null;
  check: Extract<Ev, { type: "check" }> | null;
  lastLand: { i: number; t: number } | null;
};

export function stateAt(s: number): State {
  const landed = FEEDS.map((f) => f.f0);
  const fetching: State["fetching"] = FEEDS.map(() => null);
  let build: State["build"] = null;
  let check: State["check"] = null;
  let lastLand: State["lastLand"] = null;
  for (const e of EVENTS) {
    if (e.t > s) break;
    if (e.type === "fetch") fetching[e.i] = Math.min(1, (s - e.t) / LAND);
    else if (e.type === "land") {
      landed[e.i] = e.t;
      fetching[e.i] = null;
      lastLand = { i: e.i, t: e.t };
    } else if (e.type === "build") build = e;
    else check = e;
  }
  return { s, age: landed.map((l) => s - l), fetching, build, check, lastLand };
}

export const due = (st: State, i: number) => st.age[i] >= FEEDS[i].ttl;

// An example clock for the readout.
const T0 = 8 * 3600 + 14 * 60;
export function clock(s: number) {
  const c = Math.floor(T0 + s);
  const h = Math.floor(c / 3600);
  const m = Math.floor((c % 3600) / 60);
  const x = c % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}`;
}

// The readout: the newest thing that happened, in plain words.
export function sayAt(st: State): string {
  const { s, build, check } = st;
  const items: { t: number; text: string }[] = [];
  if (build)
    items.push({
      t: build.t,
      text:
        build.upload === "changed"
          ? "combined: something changed, new file published"
          : build.upload === "refresh"
            ? "combined: no change in a minute, file re-sent with a new time"
            : "combined: nothing changed, file left as is",
    });
  if (check) items.push({ t: check.t, text: check.got ? "your map downloaded the new file" : "your map checked: nothing new" });
  if (st.lastLand) items.push({ t: st.lastLand.t, text: `${FEEDS[st.lastLand.i].name.toLowerCase()}: new copy in` });
  FEEDS.forEach((f, i) => {
    if (st.fetching[i] !== null) items.push({ t: s - (st.fetching[i] ?? 0) * LAND, text: `${f.name.toLowerCase()}: fetching a new copy` });
  });
  if (!items.length) return clock(s);
  const last = items.reduce((a, b) => (b.t >= a.t ? b : a));
  return `${clock(last.t)} ${last.text}`;
}

// The still picture (reduced motion, no JS, off screen): the moment after a map download
// where the copies' ages are most spread out and at least one copy is due.
export const STILL = (() => {
  let best = CHECK_AT + CARRY;
  let score = -1;
  for (const e of EVENTS) {
    if (e.t > 3600) break;
    if (e.type !== "check" || !e.got) continue;
    const st = stateAt(e.t + CARRY);
    const f = st.age.map((a, i) => Math.min(1, a / FEEDS[i].ttl));
    const dueCount = f.filter((x) => x >= 1).length;
    if (dueCount !== 1) continue;
    const sorted = [...f].sort((a, b) => a - b);
    let spread = 1;
    for (let k = 1; k < sorted.length; k++) spread = Math.min(spread, sorted[k] - sorted[k - 1]);
    if (spread > score) {
      score = spread;
      best = e.t + CARRY;
    }
  }
  return best;
})();
