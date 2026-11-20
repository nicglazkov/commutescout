// Data helpers for the plugin marketplace: the catalog's shape as
// /api/flare/sources sends it, this browser's install switches, the alert
// kind groups and the facet logic. No React here.

export type Tier = "approved" | "unreviewed" | "private";

export type Source = {
  id: string;
  name: string;
  visibility?: "public" | "unlisted" | null;
  description?: string | null;
  attribution?: { name?: string; url?: string } | null;
  tier?: Tier | null;
  count?: number;
  ok?: boolean | null;
  coverage?: number[] | null;
  kinds?: string[];
  capabilities?: Record<string, boolean>;
  refresh_s?: number | null;
  version?: string | null;
  base?: string | null;
};

// ---- this browser's install switches (the map reads the same keys) ----

export const OFF_KEY = "cs.plugins.off"; // ids switched off in this browser, comma separated
export const ON_KEY = "cs.plugins.on"; // unlisted ids installed in this browser

export function idSet(key: string): Set<string> {
  try {
    return new Set((localStorage.getItem(key) || "").split(",").filter(Boolean));
  } catch {
    return new Set();
  }
}

export function saveSet(key: string, ids: Set<string>) {
  try {
    localStorage.setItem(key, Array.from(ids).join(","));
  } catch {
    /* private mode */
  }
}

// ---- labels ----

export function tierOf(s: Source): Tier {
  return s.tier === "approved" || s.tier === "private" ? s.tier : "unreviewed";
}

export function coverageLabel(b?: number[] | null): string {
  if (!b || b.length !== 4) return "Not stated";
  const [s, w, n, e] = b;
  const h = n - s,
    wd = e - w;
  if (h >= 20 && wd >= 50) return "Whole country";
  return `${Math.round(h)}° by ${Math.round(wd)}° area`;
}

export function refreshLabel(s?: number | null): string {
  if (!s || s <= 0) return "Not stated";
  if (s <= 60) return "Every minute";
  if (s < 3600) return `Every ${Math.round(s / 60)} min`;
  if (s === 3600) return "Every hour";
  return `Every ${Math.round(s / 3600)} h`;
}

export function alertsLabel(s: Source): string {
  return s.ok === false ? "Offline" : (s.count ?? 0).toLocaleString("en-US");
}

/** An operator named the same as its plugin says nothing twice. */
export function operatorOf(s: Source): string {
  const named = s.attribution?.name && s.attribution.name !== s.name ? s.attribution.name : "";
  return named || "Run by its community";
}

// ---- alert kinds, grouped the way the map legend groups them ----

export type Group = "police" | "crashes" | "hazards" | "jams" | "closures" | "weather" | "chains" | "cameras" | "other";

export const GROUP_ORDER: Group[] = ["crashes", "hazards", "closures", "weather", "chains", "jams", "police", "cameras", "other"];

/** Label and colour tone per group; the tones match the kinds list on /plugins. */
export const GROUP_META: Record<Group, { label: string; tone: string }> = {
  crashes: { label: "Crashes", tone: "incident" },
  hazards: { label: "Hazards", tone: "hazard" },
  closures: { label: "Closures", tone: "closure" },
  weather: { label: "Weather", tone: "weather" },
  chains: { label: "Chain controls", tone: "chain" },
  jams: { label: "Traffic jams", tone: "traffic" },
  police: { label: "Police", tone: "police" },
  cameras: { label: "Cameras", tone: "camera" },
  other: { label: "Other", tone: "other" },
};

export function groupOf(kind: string): Group {
  if (kind.startsWith("POLICE")) return "police";
  if (kind.startsWith("CRASH")) return "crashes";
  if (kind.startsWith("HAZARD")) return "hazards";
  if (kind.startsWith("JAM")) return "jams";
  if (kind.startsWith("ROAD_CLOSED") || kind.startsWith("LANE")) return "closures";
  if (kind.startsWith("WEATHER")) return "weather";
  if (kind.startsWith("CAMERA")) return "cameras";
  if (kind.startsWith("CHAINS")) return "chains";
  return "other";
}

/** The groups a plugin sends, in display order, with how many kinds each covers. */
export function groupsOf(s: Source): { group: Group; n: number }[] {
  const m = new Map<Group, number>();
  for (const k of s.kinds || []) m.set(groupOf(k), (m.get(groupOf(k)) || 0) + 1);
  return GROUP_ORDER.filter((g) => m.has(g)).map((g) => ({ group: g, n: m.get(g)! }));
}

/** What a plugin is mostly about: picks its icon, the way a store listing has an app icon. */
export function mainGroup(s: Source): Group | "crowd" {
  const k = s.kinds || [];
  const gs = groupsOf(s);
  if (gs.length === 1) return gs[0].group;
  if (k.some((x) => /^(POLICE|CRASH|HAZARD)/.test(x))) return "crowd";
  return gs[0]?.group ?? "other";
}

// ---- facets ----

export const CAPS: { id: string; label: string }[] = [
  { id: "report", label: "Takes new reports" },
  { id: "confirm", label: "Asks you to confirm reports" },
];

export type FacetId = "trust" | "shows" | "can" | "coverage";
export type Filters = Record<FacetId, Set<string>> & { installed: boolean; q: string };

export const emptyFilters = (): Filters => ({
  trust: new Set(),
  shows: new Set(),
  can: new Set(),
  coverage: new Set(),
  installed: false,
  q: "",
});

/** The facet values a plugin carries, per facet. */
export function valuesOf(s: Source): Record<FacetId, string[]> {
  return {
    trust: [tierOf(s)],
    shows: groupsOf(s).map((g) => g.group),
    can: CAPS.filter((c) => s.capabilities?.[c.id]).map((c) => c.id),
    coverage: [coverageLabel(s.coverage)],
  };
}

function matchesQuery(s: Source, q: string): boolean {
  if (!q) return true;
  const hay = [s.name, s.description, s.attribution?.name, ...groupsOf(s).map((g) => GROUP_META[g.group].label)]
    .join(" ")
    .toLowerCase();
  return q
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => hay.includes(w));
}

/**
 * Whether a plugin passes every active filter. Values inside one facet are
 * OR'd, facets are AND'd. `skip` leaves one facet out, which is how each
 * facet's counts are worked out against the other filters.
 */
export function passes(s: Source, f: Filters, installed: boolean, skip?: FacetId): boolean {
  if (f.installed && !installed) return false;
  if (!matchesQuery(s, f.q)) return false;
  const v = valuesOf(s);
  for (const id of ["trust", "shows", "can", "coverage"] as FacetId[]) {
    if (id === skip || f[id].size === 0) continue;
    if (!v[id].some((x) => f[id].has(x))) return false;
  }
  return true;
}

export function activeCount(f: Filters): number {
  return f.trust.size + f.shows.size + f.can.size + f.coverage.size + (f.installed ? 1 : 0);
}
