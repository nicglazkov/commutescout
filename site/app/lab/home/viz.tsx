"use client";

import { useEffect, useState } from "react";
import { STATE_COVERAGE, type StateRow } from "@/lib/state-coverage";
import { US_NATION, US_STATES, US_VIEWBOX } from "@/components/figures/us-map.geo";
import { decodeMarkers, type Marker } from "./albers";
import { MARKERS, STATS } from "./live-snapshot";

// Shared drawing pieces for the home board: the real US geometry, the
// snapshot markers drawn as one path per kind, live counts from /api/stats
// (public, no key, exempt from the rate limiter) with the snapshot as a
// fallback, and per-state coverage depth from lib/state-coverage.ts.

export const KIND = {
  i: { label: "Incidents", stroke: "var(--cs-incident)", soft: "var(--cs-incident-soft)" },
  c: { label: "Closures", stroke: "var(--cs-closure)", soft: "var(--cs-closure-soft)" },
  h: { label: "Chain controls", stroke: "var(--cs-chain)", soft: "var(--cs-chain-soft)" },
  f: { label: "Wildfires", stroke: "var(--cs-fire)", soft: "var(--cs-fire-soft)" },
} as const;
export type KindKey = keyof typeof KIND;

let cache: Marker[] | null = null;
export function markers(): Marker[] {
  if (!cache) cache = decodeMarkers(MARKERS);
  return cache;
}

export function dotPath(ms: Marker[]): string {
  let d = "";
  for (const m of ms) d += `M${m.x.toFixed(1)} ${m.y.toFixed(1)}h0`;
  return d;
}

export type Stats = {
  incidents: number;
  closures: number;
  chain_controls: number;
  wildfires: number;
  cameras: number;
  sources: number;
  states: number;
};

/** Live counts from the public stats endpoint; the snapshot until it answers. */
export function useLiveStats(): { stats: Stats; live: boolean } {
  const [s, setS] = useState<{ stats: Stats; live: boolean }>({ stats: STATS, live: false });
  useEffect(() => {
    let off = false;
    const load = () =>
      fetch("/api/stats", { headers: { Accept: "application/json" } })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((d: Stats) => {
          if (!off) setS({ stats: d, live: true });
        })
        .catch(() => {});
    load();
    const t = window.setInterval(load, 30000);
    return () => {
      off = true;
      window.clearInterval(t);
    };
  }, []);
  return s;
}

export const fmt = (n: number) => n.toLocaleString("en-US");

/* ---------------- Coverage depth ---------------- */

export const LAYERS: { key: keyof StateRow; label: string; short: string }[] = [
  { key: "incidents", label: "Incidents", short: "Inc" },
  { key: "closures", label: "Closures", short: "Clo" },
  { key: "cameras", label: "Cameras", short: "Cam" },
  { key: "signs", label: "Message signs", short: "Sgn" },
  { key: "weather", label: "Road weather", short: "Wx" },
  { key: "chains", label: "Chain controls", short: "Chn" },
];

export const has = (v: string) => v.startsWith("Y");
export const baseName = (s: string) => s.replace(/\s*\(.*\)$/, "");

export const ROW_BY_NAME: Record<string, StateRow> = Object.fromEntries(
  STATE_COVERAGE.map((r) => [baseName(r.state), r]),
);

/** How many of the five everyday layers a state's own feeds publish (chains are seasonal). */
export function depth(name: string): number {
  const r = ROW_BY_NAME[name];
  if (!r) return -1;
  return (["incidents", "closures", "cameras", "signs", "weather"] as const).filter((k) => has(r[k])).length;
}

export const POSTAL: Record<string, string> = {
  Alabama: "AL", Alaska: "AK", Arizona: "AZ", Arkansas: "AR", California: "CA", Colorado: "CO",
  Connecticut: "CT", Delaware: "DE", "District of Columbia": "DC", Florida: "FL", Georgia: "GA",
  Hawaii: "HI", Idaho: "ID", Illinois: "IL", Indiana: "IN", Iowa: "IA", Kansas: "KS", Kentucky: "KY",
  Louisiana: "LA", Maine: "ME", Maryland: "MD", Massachusetts: "MA", Michigan: "MI", Minnesota: "MN",
  Mississippi: "MS", Missouri: "MO", Montana: "MT", Nebraska: "NE", Nevada: "NV", "New Hampshire": "NH",
  "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
  Ohio: "OH", Oklahoma: "OK", Oregon: "OR", Pennsylvania: "PA", "Rhode Island": "RI",
  "South Carolina": "SC", "South Dakota": "SD", Tennessee: "TN", Texas: "TX", Utah: "UT", Vermont: "VT",
  Virginia: "VA", Washington: "WA", "West Virginia": "WV", Wisconsin: "WI", Wyoming: "WY",
};
export const NAME_BY_POSTAL: Record<string, string> = Object.fromEntries(
  Object.entries(POSTAL).map(([n, c]) => [c, n]),
);

/** Fill for a depth tier: accent ramp built from the accent and the surface (no new hues). */
export function depthFill(d: number): string {
  if (d < 0) return "var(--cs-surface-2)";
  const pct = [18, 32, 50, 72, 100][Math.max(0, Math.min(4, d - 1))] ?? 18;
  return `color-mix(in oklab, var(--cs-accent) ${pct}%, var(--cs-surface))`;
}

/* ---------------- The map ---------------- */

/** Just the state outlines, for use inside another svg. */
export function StatePaths({ fill = "var(--cs-surface-2)", stroke = "var(--cs-line-strong)" }: { fill?: string; stroke?: string }) {
  return (
    <g>
      {US_STATES.map((s) => (
        <path key={s.id} d={s.d} fill={fill} stroke={stroke} strokeWidth={0.8} strokeLinejoin="round" />
      ))}
    </g>
  );
}

export function UsMap({
  fill = () => "var(--cs-surface)",
  stroke = "var(--cs-line-strong)",
  showDots,
  dotKinds = ["c", "i", "h", "f"],
  dotSize = 3,
  className,
  title,
  onState,
  active,
  children,
}: {
  fill?: (name: string) => string;
  stroke?: string;
  showDots?: boolean;
  dotKinds?: KindKey[];
  dotSize?: number;
  className?: string;
  title: string;
  onState?: (name: string) => void;
  active?: string | null;
  children?: React.ReactNode;
}) {
  const ms = showDots ? markers() : [];
  return (
    <svg viewBox={US_VIEWBOX} className={className} role="img" aria-label={title}>
      <path d={US_NATION} fill="var(--cs-surface-2)" />
      {US_STATES.map((s) => (
        <path
          key={s.id}
          d={s.d}
          fill={fill(s.name)}
          stroke={active === s.name ? "var(--cs-ink)" : stroke}
          strokeWidth={active === s.name ? 1.6 : 0.6}
          strokeLinejoin="round"
          onPointerEnter={onState ? () => onState(s.name) : undefined}
          onClick={onState ? () => onState(s.name) : undefined}
          style={onState ? { cursor: "pointer" } : undefined}
        >
          <title>{s.name}</title>
        </path>
      ))}
      {showDots &&
        dotKinds.map((k) => (
          <path
            key={k}
            d={dotPath(ms.filter((m) => m.k === k))}
            stroke={KIND[k].stroke}
            strokeWidth={k === "c" ? dotSize * 1.05 : dotSize * 1.6}
            strokeLinecap="round"
            fill="none"
            opacity={k === "c" ? 0.7 : 1}
          />
        ))}
      {children}
    </svg>
  );
}

export function KindKeyRow({ kinds = ["i", "c", "h", "f"] as KindKey[], counts }: { kinds?: KindKey[]; counts?: Partial<Record<KindKey, number>> }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-[0.8125rem] text-cs-ink-2">
      {kinds.map((k) => (
        <li key={k} className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-2 rounded-full" style={{ background: KIND[k].stroke }} />
          {KIND[k].label}
          {counts?.[k] !== undefined && <span className="cs-data text-cs-ink">{fmt(counts[k] as number)}</span>}
        </li>
      ))}
    </ul>
  );
}

export function useReduced(): boolean {
  const [r, setR] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setR(m.matches);
    on();
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return r;
}

/** A step counter that advances every `ms`, paused under reduced motion or when `paused`. */
export function useCycle(n: number, ms: number, paused = false): [number, (i: number) => void] {
  const reduced = useReduced();
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reduced || paused) return;
    const t = window.setInterval(() => setI((x) => (x + 1) % n), ms);
    return () => window.clearInterval(t);
  }, [n, ms, reduced, paused]);
  return [i, setI];
}
