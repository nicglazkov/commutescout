"use client";

import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { STATE_COVERAGE, STATE_COVERAGE_UPDATED, type StateRow } from "@/lib/state-coverage";
import { PointerHint, FigureFrame } from "./frame";
import { US_NATION, US_STATES, US_VIEWBOX } from "./us-map.geo";

// Coverage depth by state, on true state geography (us-atlas states-albers-10m, geoAlbersUsa,
// precomputed at build time by _build/us-map.mjs so no d3 ships to the client).
// Depth is derived, not invented: for each row of STATE_COVERAGE (site/lib/state-coverage.ts,
// transcribed from docs/state-coverage.md) count how many of the five live layers a state's own
// feeds publish: incidents, closures, cameras, message signs, road weather. Any "Y..." cell counts
// (Y, Y (wz), Y (passes), Y**). Chains are seasonal and n/a in most states, and wildfires come from the
// national WFIGS layer for every state, so neither ranks depth. States with no row still get the
// nationwide layers (wildfires, NWS alerts, the traffic overlay; see OVERLAY_NOTE / WILDFIRE_NOTE).

type Layer = { key: keyof StateRow; label: string };
const LAYERS: Layer[] = [
  { key: "incidents", label: "Crashes" },
  { key: "closures", label: "Closures" },
  { key: "cameras", label: "Cameras" },
  { key: "signs", label: "Road signs" },
  { key: "weather", label: "Road weather" },
];
const TIERS = [
  { tier: 4, label: "All five kinds", short: "All 5" },
  { tier: 3, label: "Three or four kinds", short: "3 or 4" },
  { tier: 2, label: "Two kinds", short: "2" },
  { tier: 1, label: "One kind", short: "1" },
  { tier: 0, label: "Weather and wildfires only", short: "Basics" },
] as const;
// small eastern states get a labelled key square beside the map so they stay pointable
const SMALL: [string, string][] = [
  ["Vermont", "VT"],
  ["New Hampshire", "NH"],
  ["Massachusetts", "MA"],
  ["Rhode Island", "RI"],
  ["Connecticut", "CT"],
  ["New Jersey", "NJ"],
  ["Delaware", "DE"],
  ["Maryland", "MD"],
  ["District of Columbia", "DC"],
];

const has = (v: string) => v.startsWith("Y");
const baseName = (s: string) => s.replace(/\s*\(.*\)$/, "");
const noteOf = (s: string) => (s.match(/\((.*)\)$/) || [])[1];

function cellText(v: string): string {
  if (v === "Y") return "Yes";
  if (v === "Y (wz)") return "Work zones";
  if (v === "Y (passes)") return "Mountain passes";
  if (v === "Y*") return "Yes, national feed";
  if (v === "Y**") return "Part of the state";
  if (v === "n/a") return "Not applicable";
  return "Not available";
}

type Info = { name: string; row?: StateRow; count: number; tier: number; note?: string };

export default function UsCoverageMap({ n = 2 }: { n?: number | string }) {
  const rows = useMemo(() => {
    const m = new Map<string, Info>();
    for (const row of STATE_COVERAGE) {
      const name = baseName(row.state);
      const count = LAYERS.filter((l) => has(row[l.key])).length;
      const tier = count === 5 ? 4 : count >= 3 ? 3 : count;
      m.set(name, { name, row, count, tier, note: noteOf(row.state) });
    }
    return m;
  }, []);
  const info = (name: string): Info => rows.get(name) ?? { name, count: 0, tier: 0 };
  const covered = US_STATES.filter((s) => rows.has(s.name));
  const order = useMemo(() => covered.map((s) => s.name), [covered]);
  const counts = TIERS.map((t) => US_STATES.filter((s) => info(s.name).tier === t.tier && s.name !== "District of Columbia").length);

  const stage = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<string | null>(null);
  const [focusName, setFocusName] = useState(order[0]);
  const [tip, setTip] = useState<{ x: number; y: number; w: number } | null>(null);

  const place = (name: string, clientX?: number, clientY?: number) => {
    const el = stage.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    let x: number;
    let y: number;
    if (clientX !== undefined && clientY !== undefined) {
      x = clientX - box.left;
      y = clientY - box.top;
    } else {
      const s = US_STATES.find((t) => t.name === name);
      const small = SMALL.findIndex(([full]) => full === name);
      const [cx, cy] = small >= 0 ? [956, 172 + small * 21] : s ? s.c : [487, 305];
      x = (cx / 975) * box.width;
      y = (cy / 610) * box.height;
    }
    setActive(name);
    setTip({ x, y, w: box.width });
  };
  const clear = () => {
    setActive(null);
    setTip(null);
  };
  const onMove = (e: PointerEvent<SVGElement>) => {
    const name = (e.target as Element).closest("[data-state]")?.getAttribute("data-state");
    if (!name) return clear();
    if (e.pointerType === "mouse") place(name, e.clientX, e.clientY);
  };
  const onTap = (e: PointerEvent<SVGElement>) => {
    if (e.pointerType === "mouse") return;
    const name = (e.target as Element).closest("[data-state]")?.getAttribute("data-state");
    if (name) place(name);
    else clear();
  };
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    const i = Math.max(0, order.indexOf(focusName));
    let next = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = (i + 1) % order.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = (i - 1 + order.length) % order.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = order.length - 1;
    else if (e.key === "Escape") return clear();
    else return;
    e.preventDefault();
    setFocusName(order[next]);
    place(order[next]);
  };

  const a = active ? info(active) : null;
  const tipStyle = (() => {
    if (!tip) return undefined;
    const w = tip.w;
    const tw = Math.min(260, w - 16);
    const left = Math.max(8, Math.min(tip.x + 14, w - tw - 8));
    const flip = tip.x + 14 + tw > w - 8 && tip.x - tw - 14 > 8;
    return { left: flip ? tip.x - tw - 14 : left, top: Math.max(4, tip.y + 14), width: tw };
  })();
  const shapeOf = (name: string) => US_STATES.find((s) => s.name === name);
  const activeShape = active ? shapeOf(active) : undefined;

  return (
    <FigureFrame
      n={n}
      title="How much live detail each state shares"
      className="csf-map"
      hint={<PointerHint fine="Hover or focus the map and use the arrow keys" coarse="Tap a state to see what it shares" />}
      readout={
        a
          ? `${a.name}: ${a.tier ? `${a.count} of 5 kinds` : "weather and wildfires only"}`
          : `${STATE_COVERAGE.length} states · ${counts[0]} share all five`
      }
      legend={
        <details className="csf-details">
          <summary>Coverage by state, as a table</summary>
          <div className="csf-table-wrap">
            <table className="csf-table">
              <caption className="csf-sr">What each covered state shares</caption>
              <thead>
                <tr>
                  <th scope="col">State</th>
                  {LAYERS.map((l) => (
                    <th key={l.key} scope="col">
                      {l.label}
                    </th>
                  ))}
                  <th scope="col" className="num">
                    Layers
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...rows.values()]
                  .sort((x, y) => y.count - x.count || x.name.localeCompare(y.name))
                  .map((r) => (
                    <tr key={r.name}>
                      <th scope="row">
                        {r.name}
                        {r.note ? <span className="csf-muted"> ({r.note})</span> : null}
                      </th>
                      {LAYERS.map((l) => (
                        <td key={l.key}>{r.row ? cellText(r.row[l.key]) : ""}</td>
                      ))}
                      <td className="num">{r.count}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </details>
      }
      caption={
        <>
          Stronger blue means more of five kinds of live detail: crashes, closures, cameras, road signs and road weather.
          Every state also gets weather alerts, wildfires and traffic speeds. As of {STATE_COVERAGE_UPDATED.split(" ")[0]}.
        </>
      }
    >
      <div className="csf-map-legend" aria-hidden="true">
        <span className="csf-map-legend-title">Kinds of live detail a state shares, out of 5 (number of states below)</span>
        <span className="csf-ramp">
          {[...TIERS].reverse().map((t, i) => (
            <span key={t.tier} className="csf-ramp-step">
              <span className="csf-ramp-sw" data-tier={t.tier} />
              <span className="csf-ramp-label">{t.short}</span>
              <span className="csf-ramp-n">{[...counts].reverse()[i]}</span>
            </span>
          ))}
        </span>
      </div>
      <div className="csf-map-stage" ref={stage} onPointerLeave={clear}>
        <svg
          className="csf-svg csf-focus"
          viewBox={US_VIEWBOX}
          role="img"
          tabIndex={0}
          aria-label={`Map of the United States shaded by coverage depth. Number of states by depth: ${TIERS.slice(0, 4)
            .map((t, i) => `${t.label}: ${counts[i]}`)
            .join("; ")}; the remaining states have weather and wildfires only. Use the arrow keys to step through covered states; the table below lists every state.`}
          aria-describedby="csf-map-live"
          onPointerMove={onMove}
          onPointerDown={onTap}
          onKeyDown={onKey}
          onFocus={() => place(focusName)}
          onBlur={clear}
        >
          <path className="csf-nation" d={US_NATION} />
          {US_STATES.map((s) => (
            <path key={s.id} data-state={s.name} data-tier={info(s.name).tier} className="csf-state" d={s.d} />
          ))}
          {SMALL.map(([full, ab], i) => {
            const t = info(full).tier;
            return (
              <g key={ab} data-state={full} className="csf-small">
                <rect x={944} y={164 + i * 21} width={26} height={16} rx={3} className="csf-state" data-tier={t} />
                <text x={957} y={164 + i * 21 + 11.4} textAnchor="middle" data-dark={t >= 3 ? "" : undefined}>
                  {ab}
                </text>
              </g>
            );
          })}
          {activeShape && <path className="csf-state-hi" d={activeShape.d} />}
          {active && SMALL.some(([f]) => f === active) && (
            <rect
              className="csf-state-hi"
              x={944}
              y={164 + SMALL.findIndex(([f]) => f === active) * 21}
              width={26}
              height={16}
              rx={3}
            />
          )}
        </svg>
        {a && tipStyle && (
          <div className="csf-tip" style={tipStyle} role="presentation">
            <div className="csf-tip-head">
              <b>{a.name}</b>
              <span className="csf-tip-sw" data-tier={a.tier} />
            </div>
            <div className="csf-tip-note">
              {TIERS.find((t) => t.tier === a.tier)?.label}
              {a.note ? ` · ${a.note} only` : ""}
            </div>
            {a.row ? (
              <ul className="csf-tip-list">
                {LAYERS.map((l) => {
                  const v = a.row![l.key];
                  return (
                    <li key={l.key} data-on={has(v) ? "" : undefined}>
                      <span className="csf-tip-mark" aria-hidden="true" />
                      <span>{l.label}</span>
                      {has(v) && v !== "Y" && <span className="csf-tip-q">{cellText(v).toLowerCase()}</span>}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="csf-tip-note">Wildfires, weather alerts and the traffic overlay, which cover every state.</div>
            )}
          </div>
        )}
        <p id="csf-map-live" className="csf-sr" aria-live="polite">
          {a
            ? a.row
              ? `${a.name}: ${LAYERS.map((l) => `${l.label} ${cellText(a.row![l.key]).toLowerCase()}`).join(", ")}.`
              : `${a.name}: weather and wildfires only.`
            : ""}
        </p>
      </div>
    </FigureFrame>
  );
}
