"use client";

import { useState, type KeyboardEvent } from "react";
import { PointerHint, FigureFrame } from "./frame";

// best_time_to_go, as the tool computes it (src/ca_roads_mcp/planning.py:930-1151):
// - at most 16 departures (MAX_SLOTS, planning.py:71); with no step given the window is split into
//   15-minute multiples that fit 16 slots (planning.py:1015-1017), so the default 6 AM to 9 PM window is hourly
// - each row: minutes with traffic, the forecast's driving_hazard, and usual_incidents_that_hour from the
//   route's last 90 days within 300 m (planning.py:1054, :1075-1081)
// - severe = blizzard, freezing, ice, sleet or snow (planning.py:1096-1098); severe rows cannot be best
// - best = fewest minutes, ties broken by fewer usual incidents that hour (planning.py:1100-1107)
// - good_departures: within 8% of best; avoid: 25% or more over the fastest row (planning.py:1109-1110)
// Sample values are illustrative.

type Row = { h: number; min: number; inc: number; wx?: "snow" | "rain" };
const ROWS: Row[] = [
  { h: 6, min: 42, inc: 2 },
  { h: 7, min: 52, inc: 4 },
  { h: 8, min: 63, inc: 6 },
  { h: 9, min: 58, inc: 5 },
  { h: 10, min: 47, inc: 2 },
  { h: 11, min: 44, inc: 1 },
  { h: 12, min: 43, inc: 2 },
  { h: 13, min: 42, inc: 1 },
  { h: 14, min: 44, inc: 2, wx: "rain" },
  { h: 15, min: 51, inc: 3, wx: "rain" },
  { h: 16, min: 60, inc: 5 },
  { h: 17, min: 64, inc: 7 },
  { h: 18, min: 55, inc: 4 },
  { h: 19, min: 46, inc: 2 },
  { h: 20, min: 43, inc: 1, wx: "snow" },
  { h: 21, min: 39, inc: 1, wx: "snow" },
];
const SEVERE = new Set(["snow"]);
function Wx({ kind, x, y: cy }: { kind: "snow" | "rain"; x: number; y: number }) {
  return kind === "snow" ? (
    <path className="dc-wx" data-wx="snow" d={`M${x} ${cy - 6}v12M${x - 5.2} ${cy - 3}l10.4 6M${x - 5.2} ${cy + 3}l10.4 -6`} />
  ) : (
    <path className="dc-wx" data-wx="rain" d={`M${x} ${cy - 6}c3 4 4.5 6 4.5 8a4.5 4.5 0 0 1 -9 0c0 -2 1.5 -4 4.5 -8z`} />
  );
}
const clock = (h: number) => `${h % 12 || 12}:00 ${h < 12 ? "AM" : "PM"}`;
const short = (h: number) => `${h % 12 || 12}${h < 12 ? "a" : "p"}`;

const fastest = ROWS.reduce((a, r) => (r.min < a.min ? r : a));
const candidates = ROWS.filter((r) => !r.wx || !SEVERE.has(r.wx));
const best = candidates.reduce((a, r) => (r.min < a.min || (r.min === a.min && r.inc < a.inc) ? r : a));
const goodCut = best.min * 1.08;
const avoidCut = fastest.min * 1.25;
const status = (r: Row) => (r === best ? "best" : r.min >= avoidCut ? "avoid" : r.min <= goodCut ? "good" : "ok");

// chart geometry (one axis: minutes)
const W = 1000;
const H = 300;
const L = 66;
const R = 96;
const T = 18;
const B = 64;
const YMAX = 70;
const y = (m: number) => T + (1 - m / YMAX) * (H - T - B);
const slot = (W - L - R) / ROWS.length;
const bw = Math.min(34, slot - 12);

export default function DepartureChart({ n = 5 }: { n?: number | string }) {
  const [hot, setHot] = useState<number | null>(null);
  const r = hot !== null ? ROWS[hot] : null;
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    const i = hot ?? ROWS.indexOf(best);
    let j = i;
    if (e.key === "ArrowRight") j = Math.min(ROWS.length - 1, i + 1);
    else if (e.key === "ArrowLeft") j = Math.max(0, i - 1);
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = ROWS.length - 1;
    else if (e.key === "Escape") return setHot(null);
    else return;
    e.preventDefault();
    setHot(j);
  };
  const describe = (x: Row) =>
    `${clock(x.h)}: ${x.min} min, usually ${x.inc} incident${x.inc === 1 ? "" : "s"} that hour${x.wx ? `, ${x.wx} forecast` : ""}${
      x === best ? ", best" : x.min >= avoidCut ? ", avoid" : ""
    }`;

  return (
    <FigureFrame
      n={n}
      title="Sixteen departures, one best time"
      className="csf-depart"
      hint={<PointerHint fine="Hover, or focus the chart and use the arrow keys" coarse="Tap a departure to read it" />}
      readout={r ? describe(r) : `Best ${clock(best.h)} · ${best.min} min · ${fastest.min} min at ${clock(fastest.h)} skipped for snow`}
      legend={
        <ul className="csf-keys">
          <li className="csf-key">
            <span className="csf-sw dc-sw" data-s="best" /> Best
          </li>
          <li className="csf-key">
            <span className="csf-sw dc-sw" data-s="good" /> Within 8% of best
          </li>
          <li className="csf-key">
            <span className="csf-sw dc-sw" data-s="ok" /> Other
          </li>
          <li className="csf-key">
            <span className="csf-sw dc-sw" data-s="avoid" /> 25% or more over the fastest
          </li>
          <li className="csf-key">
            <svg className="dc-key-wx" viewBox="-8 -8 16 16" aria-hidden="true">
              <Wx kind="snow" x={0} y={0} />
            </svg>
            Snow, ice or sleet forecast: never picked as best
          </li>
        </ul>
      }
      caption={
        <>
          best_time_to_go picks the fastest departure without snow or ice in the forecast. A tie goes to the hour with fewer
          incidents on this route. Sample day.
        </>
      }
    >
      <div className="dc">
        <svg
          className="csf-svg dc-svg csf-focus csf-desk"
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          tabIndex={0}
          aria-label={`Bar chart of drive time for 16 hourly departures from 6 AM to 9 PM. Best: ${describe(best)}. The fastest, ${clock(fastest.h)} at ${fastest.min} minutes, has snow forecast and is skipped. Use the arrow keys to read each departure.`}
          onKeyDown={onKey}
          onBlur={() => setHot(null)}
          onPointerLeave={(e) => { if (e.pointerType === "mouse") setHot(null); }}
        >
          {[0, 20, 40, 60].map((m) => (
            <g key={m}>
              <line x1={L} x2={W - R} y1={y(m)} y2={y(m)} className={m === 0 ? "dc-base" : "dc-grid"} />
              <text x={L - 8} y={y(m) + 4} textAnchor="end" className="dc-tick">
                {m}
              </text>
            </g>
          ))}
          <text x={L - 8} y={T - 4} textAnchor="end" className="dc-tick dc-unit">
            min
          </text>
          <line x1={L} x2={W - R} y1={y(goodCut)} y2={y(goodCut)} className="dc-ref" data-s="good" />
          <line x1={L} x2={W - R} y1={y(avoidCut)} y2={y(avoidCut)} className="dc-ref" data-s="avoid" />
          <text x={W - R + 8} y={y(avoidCut) - 2} className="dc-ref-label">
            avoid: {Math.ceil(avoidCut)}+ min
          </text>
          <text x={W - R + 8} y={y(goodCut) + 10} className="dc-ref-label">
            good: ≤ {Math.floor(goodCut)} min
          </text>
          {ROWS.map((row, i) => {
            const cx = L + slot * i + slot / 2;
            const s = status(row);
            const top = y(row.min);
            return (
              <g
                key={row.h}
                className="dc-col"
                data-s={s}
                data-hot={hot === i ? "" : undefined}
                data-dim={hot !== null && hot !== i ? "" : undefined}
                onPointerEnter={() => setHot(i)}
              >
                <rect x={L + slot * i} y={T} width={slot} height={H - T - B + 40} className="dc-hit" />
                <path
                  d={`M${cx - bw / 2} ${y(0)} V${top + 4} q0 -4 4 -4 H${cx + bw / 2 - 4} q4 0 4 4 V${y(0)} Z`}
                  className="dc-bar"
                  data-snow={row.wx === "snow" ? "" : undefined}
                />
                {(row === best || hot === i || row === fastest || (row.min === best.min && row !== best)) && (
                  <text x={cx} y={top - 8} textAnchor="middle" className="dc-val">
                    {row.min}
                  </text>
                )}
                {row.wx && <Wx kind={row.wx} x={cx} y={y(0) - 13} />}
                <text x={cx} y={y(0) + 18} textAnchor="middle" className="dc-hour">
                  {short(row.h)}
                </text>
                <g aria-hidden="true">
                  {Array.from({ length: row.inc }, (_, k) => (
                    <circle key={k} cx={cx - ((row.inc - 1) * 5) / 2 + k * 5} cy={y(0) + 34} r={1.9} className="dc-inc" />
                  ))}
                </g>
              </g>
            );
          })}
          <text x={L - 8} y={y(0) + 37} textAnchor="end" className="dc-tick">
            incidents
          </text>
          {(() => {
            const i = ROWS.indexOf(best);
            const cx = L + slot * i + slot / 2;
            return (
              <g className="dc-flag" aria-hidden="true">
                <rect x={cx - 22} y={y(best.min) - 46} width={44} height={18} rx={9} />
                <text x={cx} y={y(best.min) - 33.5} textAnchor="middle">
                  Best
                </text>
              </g>
            );
          })()}
        </svg>
        <ol className="dc-rows csf-phone" aria-label="Departures compared">
          {ROWS.map((row) => (
            <li key={row.h} className="dc-row" data-s={status(row)}>
              <span className="dc-row-h csf-mono">{short(row.h)}</span>
              <span className="dc-row-track">
                <span className="dc-row-bar" data-snow={row.wx === "snow" ? "" : undefined} style={{ width: `${(row.min / YMAX) * 100}%` }} />
                {row === best && (
                  <span className="dc-row-best" style={{ left: `calc(${(row.min / YMAX) * 100}% + 6px)` }}>
                    Best
                  </span>
                )}
              </span>
              <span className="dc-row-min csf-mono">{row.min}</span>
              <span className="dc-row-wx">
                {row.wx && (
                  <svg viewBox="-8 -8 16 16" aria-label={row.wx === "snow" ? "snow" : "rain"}>
                    <Wx kind={row.wx} x={0} y={0} />
                  </svg>
                )}
              </span>
            </li>
          ))}
        </ol>
        {/* The wrapper, not the table, is the 1px clip: a table ignores width: 1px
            and would widen the page on a phone. */}
        <div className="csf-sr">
        <table>
          <caption>Departures compared</caption>
          <thead>
            <tr>
              <th>Leave</th>
              <th>Minutes</th>
              <th>Usual incidents that hour</th>
              <th>Forecast</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.h}>
                <td>{clock(row.h)}</td>
                <td>{row.min}</td>
                <td>{row.inc}</td>
                <td>{row.wx ?? "clear"}</td>
                <td>{status(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </FigureFrame>
  );
}
