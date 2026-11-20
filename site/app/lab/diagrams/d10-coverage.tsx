"use client";

import { useState } from "react";
import { FigureFrame, PointerHint } from "@/components/figures/frame";
import { US_NATION, US_STATES, US_VIEWBOX } from "@/components/figures/us-map.geo";

// 10. Coverage map with source counts. Counted from the registries in
// ca_roads_demo/states.py as production runs them (source_status: regional portal,
// WZDx minus the four superseded by a keyed feed, keyless and keyed state feeds, toll
// feeds) plus the 7 core feeds of the deepest state. 52 by state + 1 national = 53.

type Entry = { n: number; how: string };
const PORTAL = "one shared regional portal (XML)";
const API = "the state's own feed";
const WZ = "a work-zone feed (WZDx), roadwork only";
const BY_STATE: Record<string, Entry> = {
  California: { n: 9, how: "7 core feeds plus 2 toll feeds" },
  Maine: { n: 1, how: PORTAL },
  "New Hampshire": { n: 1, how: PORTAL },
  Vermont: { n: 1, how: PORTAL },
  Washington: { n: 2, how: "the state's own feed plus toll rates" },
  Texas: { n: 3, how: "a city work-zone feed plus 2 toll feeds" },
  Maryland: { n: 2, how: "the state's own feed plus a work-zone feed" },
  Missouri: { n: 2, how: "the state's own feed plus a work-zone feed" },
  Delaware: { n: 2, how: "the state's own feed plus a work-zone feed" },
  Florida: { n: 2, how: "the state's own feed plus a work-zone feed" },
};
for (const s of ["Oregon", "Ohio", "Colorado", "Virginia", "Utah", "Arizona", "Alaska", "Connecticut", "Idaho", "Nevada", "North Carolina", "Illinois", "Alabama", "Michigan", "Tennessee", "Mississippi"])
  BY_STATE[s] = { n: 1, how: API };
for (const s of ["Iowa", "Wisconsin", "New York", "Indiana", "Minnesota", "Kansas", "New Jersey", "Kentucky", "Oklahoma", "Hawaii", "Louisiana"])
  BY_STATE[s] = { n: 1, how: WZ };

const ABBR: Record<string, string> = { Vermont: "VT", "New Hampshire": "NH", Connecticut: "CT", "New Jersey": "NJ", Delaware: "DE", Maryland: "MD" };
const SMALL = new Set(Object.keys(ABBR));
const TOTAL_STATES = Object.keys(BY_STATE).length;
const TOTAL = Object.values(BY_STATE).reduce((a, e) => a + e.n, 0) + 1;

export default function D10Coverage() {
  const [on, setOn] = useState<string | null>(null);
  const e = on ? BY_STATE[on] : null;
  return (
    <FigureFrame
      n={10}
      title="Where the 53 sources come from"
      hint={<PointerHint fine="Hover or focus a state" coarse="Tap a state" />}
      readout={on ? `${on}: ${e ? `${e.n} · ${e.how}` : "national layers only"}` : `${TOTAL - 1} state sources + 1 national = ${TOTAL}`}
      legend={
        <ul className="csf-keys">
          {[
            ["1 source", "26%"],
            ["2", "50%"],
            ["3", "72%"],
            ["9", "100%"],
          ].map(([l, p]) => (
            <li key={l} className="csf-key">
              <span className="dg-sw" style={{ background: `color-mix(in oklab, var(--f-accent) ${p}, var(--f-bg))` }} />
              {l}
            </li>
          ))}
          <li className="csf-key">
            <span className="dg-sw" style={{ background: "var(--f-grid)" }} />
            National layers only
          </li>
        </ul>
      }
      caption={
        <>
          The number on each state is how many of the 53 sources cover it. {TOTAL_STATES} states have at least one; every
          state, shaded or not, also gets the national wildfire layer, weather alerts, earthquakes and traffic speed.
          Most states publish one feed of their own; some only publish roadwork, and three share one regional portal.
        </>
      }
    >
      <div className="dgf">
        <svg className="csf-svg" viewBox={US_VIEWBOX} role="img" aria-label={`Map of the United States: ${TOTAL_STATES} states shaded by how many sources cover them, from 1 to 9.`}>
          <path d={US_NATION} fill="none" stroke="var(--f-line2)" strokeWidth={1} />
          {US_STATES.map((s) => {
            const entry = BY_STATE[s.name];
            return (
              <path
                key={s.id}
                className="st"
                d={s.d}
                data-n={entry?.n}
                data-on={on === s.name ? "" : undefined}
                tabIndex={entry ? 0 : -1}
                aria-label={`${s.name}: ${entry ? `${entry.n} source${entry.n > 1 ? "s" : ""}` : "national layers only"}`}
                onPointerEnter={() => setOn(s.name)}
                onPointerLeave={() => setOn(null)}
                onFocus={() => setOn(s.name)}
                onBlur={() => setOn(null)}
              />
            );
          })}
          {US_STATES.filter((s) => BY_STATE[s.name] && !SMALL.has(s.name)).map((s) => {
            const n = BY_STATE[s.name].n;
            return (
              <text key={s.id} className="st-n" x={s.c[0]} y={s.c[1] + 4} data-dark={n >= 3 ? "" : undefined}>
                {n}
              </text>
            );
          })}
          {/* the small eastern states, called out to the right */}
          {US_STATES.filter((s) => BY_STATE[s.name] && SMALL.has(s.name)).map((s, i) => {
            const y = 250 + i * 24;
            return (
              <g key={s.id}>
                <path className="lead" d={`M${s.c[0]} ${s.c[1]}L${910} ${y}`} />
                <circle className="lead-dot" cx={s.c[0]} cy={s.c[1]} r={2} />
                <text className="t-mono" x={916} y={y + 4}>
                  {ABBR[s.name]}
                </text>
                <text className="st-n" x={950} y={y + 4}>
                  {BY_STATE[s.name].n}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </FigureFrame>
  );
}
