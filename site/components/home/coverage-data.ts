import { STATE_COVERAGE, type StateRow } from "@/lib/state-coverage";

// Per-state coverage for the home page's state map, read from
// lib/state-coverage.ts (the docs' matrix, row for row). A state with no
// row there gets the nationwide layers only.

export const LAYERS: { key: keyof StateRow; label: string }[] = [
  { key: "incidents", label: "Incidents" },
  { key: "closures", label: "Closures" },
  { key: "cameras", label: "Cameras" },
  { key: "signs", label: "Message signs" },
  { key: "weather", label: "Road weather" },
  { key: "chains", label: "Chain controls" },
];

export const has = (v: string) => v.startsWith("Y");
const baseName = (s: string) => s.replace(/\s*\(.*\)$/, "");

export const ROW_BY_NAME: Record<string, StateRow> = Object.fromEntries(
  STATE_COVERAGE.map((r) => [baseName(r.state), r]),
);

/** A row covering only part of its state, e.g. "Texas (Austin metro)". */
export const PARTIAL = new Set(STATE_COVERAGE.filter((r) => /\(.*\)$/.test(r.state)).map((r) => baseName(r.state)));

/** How many of the five everyday layers a state's own feeds publish (chain controls are seasonal). */
export function depth(name: string): number {
  const r = ROW_BY_NAME[name];
  if (!r) return -1;
  return (["incidents", "closures", "cameras", "signs", "weather"] as const).filter((k) => has(r[k])).length;
}

/** Fill for a depth tier: a ramp from the accent into the surface, no new hues. */
export function depthFill(d: number): string {
  if (d < 0) return "var(--cs-surface-2)";
  const pct = [18, 32, 50, 72, 100][Math.max(0, Math.min(4, d - 1))] ?? 18;
  return `color-mix(in oklab, var(--cs-accent) ${pct}%, var(--cs-surface))`;
}

export function cellWord(v: string): string {
  if (v === "Y") return "Yes";
  if (v === "Y (wz)") return "Work zones";
  if (v === "Y (passes)") return "Mountain passes";
  if (v === "Y**") return "Part of the state";
  if (v === "n/a") return "Not used there";
  return "Not published";
}
