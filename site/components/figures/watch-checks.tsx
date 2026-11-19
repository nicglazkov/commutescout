"use client";

import { useEffect, useRef, useState } from "react";
import { Bell, Mail } from "lucide-react";
import { FigureFrame } from "./frame";
import { useInView, useReducedMotion } from "./hooks";

// One watch area on one map, checked three times. Rules from src/ca_roads_demo/watch.py:
// - the first check of a watch only records what is there (first_run), it never alerts
// - later checks alert once per new matching event; an id already seen stays quiet
// - only incidents, closures, chain controls and fires alert (WATCH_KINDS); signs, cameras and
//   weather never do
// - "inside" means the event's point is inside the drawn shape (watch_matches)
// - push is on and email off by default
// Calm autoplay through the three checks, no controls. Reduced motion and no JS show check 2,
// the one that sends an alert.

type Step = 1 | 2 | 3;
const CHECKS = [
  { n: 1 as Step, at: "First check", note: "Records what is already there. Nothing is sent." },
  { n: 2 as Step, at: "A few minutes later", note: "A new crash inside the area. One alert." },
  { n: 3 as Step, at: "Next check", note: "Nothing new. Nothing is sent." },
];

// smooth closed shape through points (Catmull-Rom)
function smooth(p: [number, number][]) {
  const n = p.length;
  let d = `M${p[0][0]} ${p[0][1]}`;
  for (let i = 0; i < n; i++) {
    const p0 = p[(i - 1 + n) % n], p1 = p[i], p2 = p[(i + 1) % n], p3 = p[(i + 2) % n];
    d += `C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)} ${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)} ${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ${p2[0]} ${p2[1]}`;
  }
  return d + "Z";
}
const AREA = smooth([
  [150, 70], [262, 52], [356, 82], [380, 158], [318, 214], [196, 222], [128, 166],
]);
const HWY = "M-10 236 C 90 214, 160 196, 236 160 S 380 96, 470 74 S 560 58, 590 50";
const ROADS = [
  "M120 -10 C 140 60, 170 120, 236 160 S 300 250, 320 330",
  "M410 -10 C 400 60, 390 110, 404 160 S 470 250, 520 330",
  "M-10 110 C 60 116, 120 100, 170 118",
];
const RIVER = "M-10 290 C 80 270, 150 300, 240 282 S 400 250, 590 268";

function Pin({ x, y, k, children }: { x: number; y: number; k: string; children?: React.ReactNode }) {
  return (
    <g className="wcx-pin" data-k={k} transform={`translate(${x} ${y})`}>
      <ellipse className="wcx-pin-shadow" cx={0} cy={1} rx={6} ry={2.2} />
      <path className="wcx-pin-body" d="M0 0 C -2 -6, -10 -10, -10 -18 A 10 10 0 1 1 10 -18 C 10 -10, 2 -6, 0 0 Z" />
      <g transform="translate(0 -18)">{children}</g>
    </g>
  );
}
const Excl = () => (
  <>
    <path className="wcx-glyph" d="M0 -4.5 V1" />
    <circle className="wcx-glyph-dot" cy={4} r={1.1} />
  </>
);

export default function WatchChecks({ n = 3 }: { n?: number | string }) {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const inView = useInView(root);
  const play = inView && !reduced;
  const [tick, setTick] = useState<Step>(1);
  const step: Step = play ? tick : 2;

  useEffect(() => {
    if (!play) return;
    const id = window.setInterval(() => setTick((t) => ((t % 3) + 1) as Step), 3600);
    return () => window.clearInterval(id);
  }, [play]);

  return (
    <FigureFrame
      n={n}
      title="A watch area, checked over time"
      className="csf-watch"
      legend={
        <ul className="csf-keys">
          <li className="csf-key"><span className="csf-sw wcx-sw" data-k="area" /> Your watch area</li>
          <li className="csf-key"><span className="csf-sw wcx-sw" data-k="incident" /> Crash</li>
          <li className="csf-key"><span className="csf-sw wcx-sw" data-k="closure" /> Closure</li>
          <li className="csf-key"><span className="csf-sw wcx-sw" data-k="sign" /> Road sign</li>
        </ul>
      }
      caption={
        <>
          The first check only records what is already there, so a new watch never sends old news. After that you get one alert
          for each <b>new</b> crash, closure, chain control or wildfire inside your area. Anything outside, and signs, cameras
          and weather, never alert.
        </>
      }
    >
      <div ref={root} className="wcx" data-step={step}>
        <svg viewBox="0 0 580 300" className="csf-svg wcx-map" role="img" aria-label="A map with a watch area drawn over a highway. One crash inside was already there, a new crash appears inside, a closure sits outside the area and a road sign sits inside.">
          <defs>
            <clipPath id="wcx-clip">
              <rect x={0} y={0} width={580} height={300} rx={12} />
            </clipPath>
          </defs>
          <g clipPath="url(#wcx-clip)">
            <rect width={580} height={300} className="wcx-land" />
            <path d="M440 180 C 500 170, 560 190, 600 180 L 600 320 L 430 320 C 420 260, 420 200, 440 180 Z" className="wcx-park" />
            <path d={RIVER} className="wcx-river" />
            {ROADS.map((d) => (
              <g key={d}>
                <path d={d} className="wcx-road-case" />
                <path d={d} className="wcx-road" />
              </g>
            ))}
            <path d={HWY} className="wcx-hwy-case" />
            <path d={HWY} className="wcx-hwy" />
            <path d={AREA} className="wcx-area" />
            <path d={AREA} className="wcx-area-edge" />
          </g>
          <rect x={0.5} y={0.5} width={579} height={299} rx={12} className="wcx-frame" />

          {/* the road sign, inside: never alerts */}
          <g className="wcx-sign" transform="translate(280 136)">
            <path d="M0 0 V12" className="wcx-sign-post" />
            <rect x={-13} y={-10} width={26} height={12} rx={2} className="wcx-sign-board" />
            <path d="M-8 -6 H8 M-8 -2.5 H4" className="wcx-sign-ink" />
          </g>
          {/* the closure, outside the area */}
          <g className="wcx-out">
            <Pin x={470} y={74} k="closure">
              <path className="wcx-glyph" d="M-4.5 0 H4.5" />
            </Pin>
            <text x={470} y={98} textAnchor="middle" className="wcx-note">outside</text>
          </g>
          {/* the crash that was already there */}
          <g className="wcx-old">
            <Pin x={196} y={182} k="incident">
              <Excl />
            </Pin>
            <text x={196} y={206} textAnchor="middle" className="wcx-note">already seen</text>
          </g>
          {/* the new crash */}
          <g className="wcx-new" transform="translate(352 113)">
            <circle className="wcx-ring" cx={0} cy={-18} r={14} />
            <g className="wcx-drop">
              <Pin x={0} y={0} k="incident">
                <Excl />
              </Pin>
            </g>
          </g>
        </svg>

        <div className="wcx-side">
          <ol className="wcx-steps">
            {CHECKS.map((c) => (
              <li key={c.n} className="wcx-step" data-on={step === c.n ? "" : undefined} data-past={step > c.n ? "" : undefined}>
                <span className="wcx-dot" aria-hidden="true" />
                <span className="wcx-step-at">{c.at}</span>
                <span className="wcx-step-note">{c.note}</span>
              </li>
            ))}
          </ol>
          <div className="wcx-card" aria-hidden={step !== 2}>
            <div className="wcx-card-head">
              <span className="wcx-card-app">CommuteScout</span>
              <span className="wcx-card-time">now</span>
            </div>
            <b>New crash in Commute</b>
            <span>Right lane blocked on the highway, inside your watch area.</span>
          </div>
          <ul className="wcx-ch" aria-label="Where alerts go">
            <li data-on="">
              <Bell size={13} aria-hidden="true" /> Push on
            </li>
            <li>
              <Mail size={13} aria-hidden="true" /> Email off
            </li>
          </ul>
        </div>
      </div>
    </FigureFrame>
  );
}
