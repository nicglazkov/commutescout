"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowRight, Check, Minus } from "lucide-react";
import { STATE_COVERAGE } from "@/lib/state-coverage";
import { BY_STATE, SOURCES_SUMMARY, SOURCE_ROWS } from "./live-snapshot";
import { KIND, LAYERS, NAME_BY_POSTAL, POSTAL, ROW_BY_NAME, UsMap, baseName, depth, depthFill, fmt, has, useLiveStats, type KindKey } from "./viz";

// Options for the panel beside "Clear answers, state by state." Every figure
// is read from lib/state-coverage.ts (the docs' matrix), /api/stats or
// /api/sources (snapshot, refreshed live where noted).

export function CoverageShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong bg-cs-surface-2/50">
      <div className="cs-container grid gap-12 py-16 md:py-20 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          <p className="cs-h2">Clear answers, state by state.</p>
          <p className="cs-lede mt-5 max-w-[30rem]">
            Road reports come from each state&rsquo;s own agencies. Weather alerts, wildfires and live traffic
            cover the whole country.
          </p>
          <span className="cs-link mt-7 inline-flex min-h-6 items-center gap-1 text-[0.9375rem]">
            See the sources for each state
            <ArrowRight aria-hidden className="size-3.5" />
          </span>
        </div>
        <div className="min-w-0 lg:col-span-7">{children}</div>
      </div>
    </div>
  );
}

function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface ${className}`}>{children}</div>;
}

const NATIONWIDE = ["Weather alerts", "Wildfires", "Live traffic"];

function cellWord(v: string): string {
  if (v === "Y") return "Yes";
  if (v === "Y (wz)") return "Work zones";
  if (v === "Y (passes)") return "Mountain passes";
  if (v === "Y**") return "Part of the state";
  if (v === "n/a") return "Not used there";
  return "Not published";
}

function DepthScale() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-cs-ink-3">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-5 rounded-sm border border-cs-line" style={{ background: depthFill(-1) }} />
        Nationwide layers only
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="flex">
          {[1, 2, 3, 4, 5].map((d) => (
            <span key={d} className="h-2.5 w-5 first:rounded-l-sm last:rounded-r-sm" style={{ background: depthFill(d) }} />
          ))}
        </span>
        1 to 5 kinds from the state
      </span>
    </div>
  );
}

/* ---------------- B01 Map with a state readout ---------------- */

export function MapReadout() {
  const [st, setSt] = useState<string>("Ohio");
  const row = ROW_BY_NAME[st];
  return (
    <Panel>
      <div className="grid sm:grid-cols-[1fr_14rem]">
        <div className="p-4">
          <UsMap
            fill={(n) => depthFill(depth(n))}
            stroke="var(--cs-surface)"
            onState={setSt}
            active={st}
            title="US map shaded by how many kinds of road report each state publishes. Hover or tap a state."
            className="block h-auto w-full"
          />
          <div className="mt-2">
            <DepthScale />
          </div>
        </div>
        <div className="border-t border-cs-line p-5 sm:border-l sm:border-t-0" aria-live="polite">
          <p className="cs-eyebrow">{row ? "From the state" : "Nationwide only"}</p>
          <p className="mt-1 text-lg font-semibold text-cs-ink">{st}</p>
          <ul className="mt-3 space-y-1.5 text-[0.8125rem]">
            {LAYERS.map((l) => {
              const v = row?.[l.key] ?? "-";
              const yes = has(v);
              return (
                <li key={l.key} className="flex items-center justify-between gap-2">
                  <span className={yes ? "text-cs-ink" : "text-cs-ink-3"}>{l.label}</span>
                  {yes ? (
                    <span className="inline-flex items-center gap-1 text-cs-ok">
                      {v !== "Y" && <span className="text-[0.75rem] text-cs-ink-3">{cellWord(v)}</span>}
                      <Check aria-label="yes" className="size-3.5" />
                    </span>
                  ) : (
                    <Minus aria-label="no" className="size-3.5 text-cs-ink-3" />
                  )}
                </li>
              );
            })}
          </ul>
          <p className="mt-4 border-t border-cs-line pt-3 text-xs leading-relaxed text-cs-ink-3">Plus weather alerts, wildfires and live traffic, in every state.</p>
        </div>
      </div>
    </Panel>
  );
}

/* ---------------- B02 Matrix ---------------- */

export function Matrix() {
  const rows = STATE_COVERAGE.slice().sort((a, b) => baseName(a.state).localeCompare(baseName(b.state)));
  const half = Math.ceil(rows.length / 2);
  const cols = [rows.slice(0, half), rows.slice(half)];
  return (
    <Panel>
      <div className="flex items-center justify-between gap-3 border-b border-cs-line px-4 py-2.5 text-[0.8125rem]">
        <span className="font-medium text-cs-ink">Every state: {NATIONWIDE.join(", ").toLowerCase()}</span>
        <span className="cs-data text-cs-ink-3">{STATE_COVERAGE.length} states with more</span>
      </div>
      <div className="grid gap-x-6 px-4 py-3 sm:grid-cols-2">
        {cols.map((c, ci) => (
          <table key={ci} className="w-full text-[0.75rem]">
            <thead>
              <tr className="text-cs-ink-3">
                <th className="py-1 text-left font-normal">
                  <span className="sr-only">State</span>
                </th>
                {LAYERS.map((l) => (
                  <th key={l.key} className="cs-data w-7 py-1 text-center font-normal" title={l.label}>
                    {l.short}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {c.map((r) => (
                <tr key={r.state} className="border-t border-cs-line">
                  <th scope="row" className="py-[3px] pr-2 text-left font-normal text-cs-ink">
                    {POSTAL[baseName(r.state)] ?? r.state}
                  </th>
                  {LAYERS.map((l) => {
                    const v = r[l.key];
                    return (
                      <td key={l.key} className="py-[3px] text-center">
                        {has(v) ? (
                          <span
                            aria-label={`${l.label}: ${cellWord(v)}`}
                            className={`inline-block size-2.5 rounded-full ${v === "Y" ? "bg-cs-accent" : "border-[1.5px] border-cs-accent"}`}
                          />
                        ) : v === "n/a" ? (
                          <span aria-label={`${l.label}: not used there`} className="text-cs-ink-3">·</span>
                        ) : (
                          <span aria-label={`${l.label}: not published`} className="inline-block h-px w-2.5 bg-cs-line-strong align-middle" />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 border-t border-cs-line px-4 py-2.5 text-xs text-cs-ink-3">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-cs-accent" />Statewide</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full border-[1.5px] border-cs-accent" />Part: work zones, passes or one region</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-px w-2.5 bg-cs-line-strong" />Not published</span>
      </p>
    </Panel>
  );
}

/* ---------------- B03 Layer reach ---------------- */

export function LayerReach() {
  const reach = LAYERS.map((l) => ({
    label: l.label,
    n: STATE_COVERAGE.filter((r) => has(r[l.key])).length,
    full: STATE_COVERAGE.filter((r) => r[l.key] === "Y").length,
  }));
  const total = 50;
  const Bar = ({ label, n, full, nation }: { label: string; n: number; full?: number; nation?: boolean }) => (
    <li className="grid grid-cols-[8.5rem_1fr_4.5rem] items-center gap-3 py-2">
      <span className="text-[0.875rem] text-cs-ink">{label}</span>
      <span className="relative h-3 rounded-sm bg-cs-surface-2">
        <span className="absolute inset-y-0 left-0 rounded-sm" style={{ width: `${(n / total) * 100}%`, background: nation ? "var(--cs-ink-2)" : "color-mix(in oklab, var(--cs-accent) 45%, var(--cs-surface))" }} />
        {full !== undefined && <span className="absolute inset-y-0 left-0 rounded-sm bg-cs-accent" style={{ width: `${(full / total) * 100}%` }} />}
      </span>
      <span className="cs-data text-right text-[0.8125rem] text-cs-ink-2">{nation ? "all 50" : `${n} states`}</span>
    </li>
  );
  return (
    <Panel className="p-5">
      <p className="cs-eyebrow">Nationwide</p>
      <ul className="mt-1">
        {NATIONWIDE.map((l) => (
          <Bar key={l} label={l} n={50} nation />
        ))}
      </ul>
      <p className="cs-eyebrow mt-5">From the states</p>
      <ul className="mt-1 divide-y divide-cs-line">
        {reach.map((r) => (
          <Bar key={r.label} label={r.label} n={r.n} full={r.full} />
        ))}
      </ul>
      <p className="mt-4 flex flex-wrap gap-x-4 text-xs text-cs-ink-3">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-cs-accent" />Statewide</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm" style={{ background: "color-mix(in oklab, var(--cs-accent) 45%, var(--cs-surface))" }} />Work zones, passes or part of the state</span>
        <span>Bars out of 50 states</span>
      </p>
    </Panel>
  );
}

/* ---------------- B04 Tile grid ---------------- */

const TILES: [string, number, number][] = [
  ["AK", 0, 0], ["ME", 11, 0], ["VT", 10, 1], ["NH", 11, 1],
  ["WA", 1, 2], ["ID", 2, 2], ["MT", 3, 2], ["ND", 4, 2], ["MN", 5, 2], ["IL", 6, 2], ["WI", 7, 2], ["MI", 8, 2], ["NY", 9, 2], ["RI", 10, 2], ["MA", 11, 2],
  ["OR", 1, 3], ["NV", 2, 3], ["WY", 3, 3], ["SD", 4, 3], ["IA", 5, 3], ["IN", 6, 3], ["OH", 7, 3], ["PA", 8, 3], ["NJ", 9, 3], ["CT", 10, 3],
  ["CA", 1, 4], ["UT", 2, 4], ["CO", 3, 4], ["NE", 4, 4], ["MO", 5, 4], ["KY", 6, 4], ["WV", 7, 4], ["VA", 8, 4], ["MD", 9, 4], ["DE", 10, 4],
  ["AZ", 2, 5], ["NM", 3, 5], ["KS", 4, 5], ["AR", 5, 5], ["TN", 6, 5], ["NC", 7, 5], ["SC", 8, 5], ["DC", 9, 5],
  ["OK", 4, 6], ["LA", 5, 6], ["MS", 6, 6], ["AL", 7, 6], ["GA", 8, 6],
  ["HI", 0, 7], ["TX", 4, 7], ["FL", 9, 7],
];

export function TileGrid() {
  const [hover, setHover] = useState<string | null>(null);
  const name = hover ? NAME_BY_POSTAL[hover] : null;
  const d = name ? depth(name) : null;
  return (
    <Panel className="p-5">
      <div className="grid grid-cols-12 gap-1" role="list" aria-label="States as tiles, shaded by how many kinds of road report each publishes">
        {Array.from({ length: 8 * 12 }, (_, i) => {
          const x = i % 12, y = Math.floor(i / 12);
          const t = TILES.find((q) => q[1] === x && q[2] === y);
          if (!t) return <span key={i} aria-hidden />;
          const nm = NAME_BY_POSTAL[t[0]];
          const dp = depth(nm);
          const dark = dp >= 4;
          return (
            <button
              key={i}
              type="button"
              role="listitem"
              onPointerEnter={() => setHover(t[0])}
              onFocus={() => setHover(t[0])}
              aria-label={`${nm}: ${dp < 0 ? "nationwide layers only" : `${dp} of 5 kinds from the state`}`}
              className={`cs-data flex aspect-square items-center justify-center rounded-[4px] text-[0.6875rem] font-medium focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-cs-accent ${
                hover === t[0] ? "ring-2 ring-cs-ink" : ""
              }`}
              style={{ background: depthFill(dp), color: dark ? "var(--cs-accent-ink)" : dp < 0 ? "var(--cs-ink-3)" : "var(--cs-ink)" }}
            >
              {t[0]}
            </button>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-cs-line pt-3">
        <DepthScale />
        <p className="text-[0.8125rem] text-cs-ink-2" aria-live="polite">
          {name ? (
            <>
              <span className="font-medium text-cs-ink">{name}</span>: {d! < 0 ? "nationwide layers" : `${d} of 5 kinds`}
            </>
          ) : (
            "Hover a state"
          )}
        </p>
      </div>
    </Panel>
  );
}

/* ---------------- B05 Freshness board ---------------- */

type SrcRow = { name: string; agency: string; state: string | null; status: string; age: number | null };

export function Freshness() {
  const [rows, setRows] = useState<SrcRow[]>(SOURCE_ROWS);
  const [sum, setSum] = useState<Record<string, number>>(SOURCES_SUMMARY);
  const [live, setLive] = useState(false);
  useEffect(() => {
    const load = () =>
      fetch("/api/sources", { headers: { Accept: "application/json" } })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((d: { summary: Record<string, number>; sources: { name: string; agency: string; state_code: string | null; status: string; age_s: number | null }[] }) => {
          setRows(d.sources.map((s) => ({ name: s.name, agency: s.agency, state: s.state_code, status: s.status, age: s.age_s })));
          setSum(d.summary);
          setLive(true);
        })
        .catch(() => {});
    load();
    const t = window.setInterval(load, 30000);
    return () => window.clearInterval(t);
  }, []);
  const color = (s: string) => (s === "fresh" ? "var(--cs-ok)" : s === "live" ? "var(--cs-weather)" : s === "stale" ? "var(--cs-stale)" : "var(--cs-closure)");
  const sorted = rows.slice().sort((a, b) => (a.state ?? "").localeCompare(b.state ?? ""));
  return (
    <Panel>
      <dl className="grid grid-cols-4 border-b border-cs-line">
        {[
          ["Fresh", sum.fresh, "fresh"],
          ["Streaming", sum.live, "live"],
          ["Stale", sum.stale, "stale"],
          ["Down", sum.down, "down"],
        ].map(([l, v, s], i) => (
          <div key={l as string} className={`px-4 py-4 ${i ? "border-l border-cs-line" : ""}`}>
            <dt className="inline-flex items-center gap-1.5 text-xs text-cs-ink-3">
              <span className="size-2 rounded-full" style={{ background: color(s as string) }} />
              {l}
            </dt>
            <dd className="cs-data mt-1.5 text-[1.75rem] font-medium leading-none text-cs-ink">{v as number}</dd>
          </div>
        ))}
      </dl>
      <div className="p-4">
        <p className="mb-2 text-xs text-cs-ink-3">Every feed, by state. Hover for the agency.</p>
        <ul className="flex flex-wrap gap-1">
          {sorted.map((r) => (
            <li
              key={r.agency + r.name}
              title={`${r.agency}, ${r.name}: ${r.status}${r.age !== null ? `, read ${r.age} s ago` : ""}`}
              className="cs-data flex h-7 min-w-9 items-center justify-center rounded-[4px] px-1 text-[0.6875rem] font-medium"
              style={{ background: `color-mix(in oklab, ${color(r.status)} 16%, var(--cs-surface))`, color: "var(--cs-ink)", boxShadow: `inset 0 -2px 0 ${color(r.status)}` }}
            >
              {r.state ?? "US"}
            </li>
          ))}
        </ul>
      </div>
      <p className="flex items-center justify-between border-t border-cs-line px-4 py-2.5 text-xs text-cs-ink-3">
        <span>{live ? "Live from the status board, checked every 30 s" : "Snapshot of the status board"}</span>
        <span className="cs-data">{rows.length} feeds</span>
      </p>
    </Panel>
  );
}

/* ---------------- B06 State lookup ---------------- */

export function StateLookup() {
  const names = Object.keys(POSTAL).filter((n) => n !== "District of Columbia").sort();
  const [st, setSt] = useState("Colorado");
  const row = ROW_BY_NAME[st];
  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-3 border-b border-cs-line p-5">
        <label htmlFor="lab-state" className="text-[0.9375rem] font-medium text-cs-ink">
          What do I get in
        </label>
        <select
          id="lab-state"
          value={st}
          onChange={(e) => setSt(e.target.value)}
          className="h-10 rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface px-3 text-[0.9375rem] text-cs-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cs-accent"
        >
          {names.map((n) => (
            <option key={n}>{n}</option>
          ))}
        </select>
        <span className="text-[0.9375rem] text-cs-ink">?</span>
      </div>
      <ul className="grid grid-cols-1 divide-y divide-cs-line sm:grid-cols-2 sm:divide-y-0" aria-live="polite">
        {[...NATIONWIDE.map((l) => ({ label: l, v: "Y", nat: true })), ...LAYERS.map((l) => ({ label: l.label, v: row?.[l.key] ?? "-", nat: false }))].map((x, i) => (
          <li key={x.label} className={`flex items-center gap-3 px-5 py-3 ${i % 2 ? "sm:border-l sm:border-cs-line" : ""} ${i > 1 ? "sm:border-t sm:border-cs-line" : ""}`}>
            <span
              className={`flex size-6 shrink-0 items-center justify-center rounded-full ${has(x.v) ? "bg-cs-ok-soft text-cs-ok" : "bg-cs-surface-2 text-cs-ink-3"}`}
            >
              {has(x.v) ? <Check aria-hidden className="size-3.5" /> : <Minus aria-hidden className="size-3.5" />}
            </span>
            <span className="flex-1">
              <span className={`block text-[0.9375rem] ${has(x.v) ? "text-cs-ink" : "text-cs-ink-3"}`}>{x.label}</span>
              <span className="block text-xs text-cs-ink-3">{x.nat ? "Nationwide" : cellWord(x.v)}</span>
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/* ---------------- B07 Source types ---------------- */

function typeOf(r: { name: string; state: string | null }): string {
  if (!r.state && !r.name.startsWith("Roadwork")) return "National services";
  if (r.name.startsWith("All feeds")) return "A state DOT's full feed";
  if (r.name.startsWith("Roadwork")) return "Work zone feeds (WZDx)";
  if (r.name.startsWith("Live feeds")) return "Traffic center live feeds";
  if (r.name.startsWith("Toll")) return "Toll prices";
  return "Single-layer feeds";
}
const TYPE_TONES = ["var(--cs-ink)", "var(--cs-accent)", "color-mix(in oklab, var(--cs-accent) 55%, var(--cs-surface))", "var(--cs-ink-2)", "var(--cs-ink-3)", "var(--cs-line-strong)"];

export function SourceTypes() {
  const groups = useMemo(() => {
    const m = new Map<string, { n: number; ex: string[] }>();
    for (const r of SOURCE_ROWS) {
      const t = typeOf(r);
      const g = m.get(t) ?? { n: 0, ex: [] };
      g.n += 1;
      if (g.ex.length < 4 && !g.ex.includes(r.agency)) g.ex.push(r.agency);
      m.set(t, g);
    }
    return Array.from(m.entries()).sort((a, b) => b[1].n - a[1].n);
  }, []);
  const total = SOURCE_ROWS.length;
  return (
    <Panel className="p-5">
      <p className="text-[0.9375rem] font-medium text-cs-ink">What kind of source each feed is</p>
      <div className="mt-4 flex h-4 overflow-hidden rounded-sm">
        {groups.map(([t, g], i) => (
          <span key={t} title={`${t}: ${g.n}`} style={{ width: `${(g.n / total) * 100}%`, background: TYPE_TONES[i] }} className={i ? "border-l-2 border-cs-surface" : ""} />
        ))}
      </div>
      <ul className="mt-4 divide-y divide-cs-line">
        {groups.map(([t, g], i) => (
          <li key={t} className="grid grid-cols-[1rem_1fr_2.5rem] items-baseline gap-3 py-2.5">
            <span aria-hidden className="size-2.5 translate-y-0.5 rounded-sm" style={{ background: TYPE_TONES[i] }} />
            <span>
              <span className="block text-[0.875rem] text-cs-ink">{t}</span>
              <span className="block text-xs text-cs-ink-3">{g.ex.join(", ")}</span>
            </span>
            <span className="cs-data text-right text-[0.875rem] text-cs-ink">{g.n}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-cs-ink-3">Counts are rows on the live status board ({total}); the site&rsquo;s headline figure is 53 official sources. Reconcile before shipping.</p>
    </Panel>
  );
}

/* ---------------- B08 Right now, by kind ---------------- */

export function NowByKind() {
  const { stats, live } = useLiveStats();
  const rows: { label: string; where: string; n: number | null; c: string }[] = [
    { label: "Closures", where: "From the states", n: stats.closures, c: KIND.c.stroke },
    { label: "Incidents", where: "From the states", n: stats.incidents, c: KIND.i.stroke },
    { label: "Chain controls", where: "From the states, in season", n: stats.chain_controls, c: KIND.h.stroke },
    { label: "Cameras", where: "From the states", n: stats.cameras, c: "var(--cs-ink-3)" },
    { label: "Wildfires", where: "Nationwide", n: stats.wildfires, c: KIND.f.stroke },
    { label: "Weather alerts", where: "Nationwide", n: null, c: "var(--cs-weather)" },
    { label: "Live traffic", where: "Nationwide", n: null, c: "var(--cs-ok)" },
  ];
  return (
    <Panel>
      <div className="flex items-center justify-between border-b border-cs-line px-5 py-3 text-[0.8125rem]">
        <span className="font-medium text-cs-ink">On the map right now</span>
        <span className="cs-data text-cs-ink-3">{live ? "live, every 30 s" : "snapshot"}</span>
      </div>
      <table className="w-full text-[0.9375rem]">
        <tbody className="divide-y divide-cs-line">
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className="px-5 py-2.5 text-left font-normal text-cs-ink">
                <span className="inline-flex items-center gap-2">
                  <span aria-hidden className="size-2 rounded-full" style={{ background: r.c }} />
                  {r.label}
                </span>
              </th>
              <td className="py-2.5 text-[0.8125rem] text-cs-ink-3">{r.where}</td>
              <td className="cs-data px-5 py-2.5 text-right text-cs-ink">{r.n === null ? "on" : fmt(r.n)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

/* ---------------- B09 Proof map: where reports are right now ---------------- */

export function ProofMap() {
  const { stats } = useLiveStats();
  return (
    <Panel className="p-4">
      <UsMap
        showDots
        dotSize={2.2}
        fill={(n) => (depth(n) >= 0 ? "var(--cs-surface)" : "var(--cs-surface-2)")}
        stroke="var(--cs-line-strong)"
        title="Every live report on the map right now, over the states it comes from. Gray states get nationwide layers only."
        className="block h-auto w-full"
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-cs-line pt-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem] text-cs-ink-2">
          {(["c", "i", "h", "f"] as KindKey[]).map((k) => (
            <li key={k} className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: KIND[k].stroke }} />
              {KIND[k].label}
            </li>
          ))}
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-4 rounded-sm border border-cs-line-strong bg-cs-surface-2" />
            Nationwide layers only
          </li>
        </ul>
        <span className="cs-data text-xs text-cs-ink-3">{fmt(stats.closures + stats.incidents + stats.chain_controls + stats.wildfires)} reports</span>
      </div>
    </Panel>
  );
}

/* ---------------- B10 States ranked by live items ---------------- */

export function Ranked() {
  const list = Object.entries(BY_STATE)
    .filter(([c]) => NAME_BY_POSTAL[c])
    .sort((a, b) => b[1].items - a[1].items);
  const top = list.slice(0, 12);
  const max = top[0]?.[1].items ?? 1;
  return (
    <Panel className="p-5">
      <div className="flex items-baseline justify-between">
        <p className="text-[0.9375rem] font-medium text-cs-ink">Live items from each state&rsquo;s agencies</p>
        <p className="cs-data text-xs text-cs-ink-3">top 12 of {list.length}</p>
      </div>
      <ol className="mt-3 space-y-1.5">
        {top.map(([c, v]) => (
          <li key={c} className="grid grid-cols-[7.5rem_1fr_3.5rem] items-center gap-3 text-[0.8125rem]">
            <span className="truncate text-cs-ink">{NAME_BY_POSTAL[c]}</span>
            <span className="h-2.5 rounded-sm bg-cs-surface-2">
              <span className="block h-full rounded-sm bg-cs-accent" style={{ width: `${(v.items / max) * 100}%` }} />
            </span>
            <span className="cs-data text-right text-cs-ink-2">{fmt(v.items)}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 border-t border-cs-line pt-3 text-xs text-cs-ink-3">
        Incidents, closures, cameras, signs and road weather, as each state publishes them. Snapshot; the live version would read /api/sources.
      </p>
    </Panel>
  );
}

/* ---------------- B11 Two maps ---------------- */

export function TwoMaps() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {[
        { t: "Everywhere in the US", sub: NATIONWIDE.join(", "), fill: () => "color-mix(in oklab, var(--cs-accent) 55%, var(--cs-surface))", n: "50 states" },
        {
          t: `In ${STATE_COVERAGE.length} states`,
          sub: "Incidents, closures, cameras, signs, road weather, chain controls",
          fill: (nm: string) =>
            nm === "Texas" ? "color-mix(in oklab, var(--cs-accent) 35%, var(--cs-surface))" : depth(nm) >= 0 ? "var(--cs-accent)" : "var(--cs-surface-2)",
          n: "Texas: the Austin metro only",
        },
      ].map((m) => (
        <Panel key={m.t} className="p-4">
          <UsMap fill={m.fill} stroke="var(--cs-surface)" title={`${m.t}: ${m.sub}`} className="block h-auto w-full" />
          <p className="mt-3 text-[0.9375rem] font-semibold text-cs-ink">{m.t}</p>
          <p className="mt-0.5 text-[0.8125rem] leading-snug text-cs-ink-2">{m.sub}</p>
          <p className="cs-data mt-2 text-xs text-cs-ink-3">{m.n}</p>
        </Panel>
      ))}
    </div>
  );
}

