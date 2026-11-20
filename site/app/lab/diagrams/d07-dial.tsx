"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay, useLoop } from "./use-play";

// 7. Data-age dial. Outer ring: one state feed's copy in memory (ca_roads/cache.py with
// states.TTL 180 s, MAX_SERVE 1800 s): fresh, then served while refreshing; a copy that keeps
// ageing means its refreshes are failing, so it is served marked stale until 30 min, then
// dropped. Inner ring: the map's "Data as of" chip on the published file's age
// (map-app.js paintAsOf: plain under 2 min, "stale" from 2, "old" from 15).

const CX = 170;
const CY = 168;
const SPAN = 30; // minutes around the dial

const pol = (r: number, min: number): [number, number] => {
  const a = (min / SPAN) * 2 * Math.PI - Math.PI / 2;
  return [Math.round((CX + r * Math.cos(a)) * 100) / 100, Math.round((CY + r * Math.sin(a)) * 100) / 100];
};
const arc = (r: number, a: number, b: number) => {
  const [x0, y0] = pol(r, a);
  const [x1, y1] = pol(r, b);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 ${b - a > SPAN / 2 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
};

const OUTER = [
  { a: 0, b: 3, k: "ok", title: "Under 3 min: fresh", body: "served as is" },
  { a: 3, b: 29.7, k: "stale", title: "3 to 30 min: refresh failing", body: "last good copy still served, marked stale" },
  { a: 29.7, b: 30, k: "incident", title: "30 min: dropped", body: "nothing served for this source" },
];
const INNER = [
  { a: 0, b: 2, k: "ok", title: "Under 2 min", body: "“Data as of 8:15”" },
  { a: 2, b: 15, k: "fire", title: "2 to 15 min", body: "amber, “(4 min ago)”" },
  { a: 15, b: 30, k: "incident", title: "15 min and older", body: "red, “(22 min ago)”" },
];

export default function D07Dial() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const t = useLoop(play, 30, 8 / 30);
  const min = t * SPAN;
  const on = (seg: { a: number; b: number }) => min >= seg.a && (min < seg.b || (seg.b === 30 && min <= 30));
  const outerOn = min >= 29.7 ? OUTER[2] : OUTER.find(on);
  const innerOn = INNER.find(on);
  const [hx, hy] = pol(138, min);
  return (
    <FigureFrame
      n={7}
      title="How old is too old"
      hint="Outer ring: one source's copy. Inner ring: the map's “Data as of” chip"
      readout={`age ${Math.floor(min)} min ${String(Math.floor((min % 1) * 60)).padStart(2, "0")} s`}
      caption={
        <>
          A source is read again once its copy is older than its refresh time, so a healthy copy never gets far round the
          dial. A copy that keeps ageing means its refreshes are failing: it stays on the map marked stale until its keep
          time, then it is dropped. The chip on the map says how old the published file is, and changes colour at 2 and
          15 minutes.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <svg className="csf-svg" viewBox="0 0 720 340" role="img" aria-label="A 30-minute dial. Outer ring for one state feed: under 3 minutes fresh, 3 to 30 minutes refresh failing and served marked stale, at 30 minutes dropped. Inner ring for the map's Data as of chip: plain under 2 minutes, amber from 2, red from 15.">
          {/* minute ticks */}
          {Array.from({ length: 30 }, (_, m) => {
            const [x0, y0] = pol(150, m);
            const [x1, y1] = pol(m % 5 === 0 ? 158 : 154, m);
            return <line key={m} className="rule" x1={x0} y1={y0} x2={x1} y2={y1} />;
          })}
          {[0, 5, 10, 15, 20, 25].map((m) => {
            const [x, y] = pol(170, m);
            return (
              <text key={m} className="t-mono" x={x} y={y + 3.5} textAnchor="middle">
                {m === 0 ? "0" : `${m} min`}
              </text>
            );
          })}
          {OUTER.map((s) => (
            <path key={s.title} data-k={s.k} d={arc(132, s.a, s.b)} fill="none" stroke="var(--k)" strokeWidth={16} opacity={outerOn === s ? 1 : 0.45} />
          ))}
          {INNER.map((s) => (
            <path key={s.title} data-k={s.k} d={arc(106, s.a, s.b)} fill="none" stroke="var(--k)" strokeWidth={10} opacity={innerOn === s ? 1 : 0.35} />
          ))}
          <circle cx={CX} cy={CY} r={86} fill="var(--f-bg)" stroke="var(--f-line)" />
          <text className="t-head" x={CX} y={CY - 18} textAnchor="middle">age</text>
          <text className="t-strong" x={CX} y={CY + 8} textAnchor="middle" style={{ fontSize: 22, fontVariantNumeric: "tabular-nums" }}>
            {Math.floor(min)}:{String(Math.floor((min % 1) * 60)).padStart(2, "0")}
          </text>
          <text className="t-mono" x={CX} y={CY + 26} textAnchor="middle">min : s</text>
          <line className="hand" x1={CX} y1={CY} x2={hx} y2={hy} strokeDasharray="0 86 200" />
          <circle cx={hx} cy={hy} r={4} fill="var(--f-ink)" />

          {/* the two keys */}
          {[
            { head: "One source's copy in memory (a state feed)", rows: OUTER, onRow: outerOn, y: 40 },
            { head: "The map's “Data as of” chip", rows: INNER, onRow: innerOn, y: 196 },
          ].map((g) => (
            <g key={g.head}>
              <text className="t-head" x={372} y={g.y}>{g.head}</text>
              {g.rows.map((r, i) => {
                const active = g.onRow === r;
                const y = g.y + 22 + i * 40;
                return (
                  <g key={r.title} data-k={r.k} opacity={active ? 1 : 0.55}>
                    <rect className="bar-k" x={372} y={y - 10} width={4} height={30} rx={2} />
                    <text className={active ? "t-strong" : undefined} x={386} y={y}>{r.title}</text>
                    <text className="t-small" x={386} y={y + 15}>{r.body}</text>
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
      </div>
    </FigureFrame>
  );
}
