"use client";

import { useRef } from "react";
import { FigureFrame } from "./frame";
import { useInView, useReducedMotion } from "./hooks";

// How sources become one map: a light table with clear map sheets on registration pins. Each sheet
// is one kind of official feed. In a calm loop the sheets lower onto the base map, so every marker
// lands on the same road, then lift apart again. Reduced motion, no JS and off screen: the sheets
// stay apart and still.
// Isometric camera: azimuth 45 degrees, elevation 30 degrees. World x and y on the table, z up.
// The sample map is drawn, not a real place.

const C = Math.cos(Math.PI / 6);
const S = Math.sin(Math.PI / 6);
const W = 400;
const D = 280;
const T = 16; // table thickness
type P3 = [number, number, number?];
const pr = ([x, y, z = 0]: P3) => [(x - y) * C, (x + y) * S - z] as const;
const pts = (a: P3[]) => a.map((p) => pr(p).map((v) => v.toFixed(1)).join(",")).join(" ");
const path = (a: P3[]) => "M" + a.map((p) => pr(p).map((v) => v.toFixed(1)).join(" ")).join("L");
const curve = (a: P3[]) => {
  // Catmull-Rom through the points, as cubic Beziers, in screen space
  const q = a.map(pr);
  let d = `M${q[0][0].toFixed(1)} ${q[0][1].toFixed(1)}`;
  for (let i = 0; i < q.length - 1; i++) {
    const p0 = q[Math.max(0, i - 1)], p1 = q[i], p2 = q[i + 1], p3 = q[Math.min(q.length - 1, i + 2)];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
};

// the sample map, in table units
const HWY: P3[] = [[18, 232], [80, 214], [140, 176], [196, 160], [250, 118], [312, 92], [382, 40]];
const ROADS: P3[][] = [
  [[60, 30], [92, 110], [140, 176], [160, 262]],
  [[230, 270], [250, 200], [250, 118], [232, 22]],
  [[312, 92], [356, 160], [384, 250]],
];
const RIVER: P3[] = [[0, 120], [60, 140], [120, 112], [190, 90], [230, 60], [290, 40], [330, 0]];
const LAKE: P3[] = [[300, 196], [330, 182], [350, 200], [338, 226], [306, 228], [292, 212]];
const TOWNS: P3[] = [[80, 214], [196, 160], [312, 92]];

// a point on the highway, t from 0 to 1 by vertex index (good enough for markers)
const onHwy = (t: number): P3 => {
  const f = t * (HWY.length - 1), i = Math.min(HWY.length - 2, Math.floor(f)), u = f - i;
  return [HWY[i][0] + (HWY[i + 1][0] - HWY[i][0]) * u, HWY[i][1] + (HWY[i + 1][1] - HWY[i][1]) * u];
};
const seg = (a: number, b: number, n = 8): P3[] => Array.from({ length: n + 1 }, (_, k) => onHwy(a + ((b - a) * k) / n));

// sheets: merged height z0, apart lift in screen px, and the delay of each one's descent
const SHEETS = [
  { id: "incident", z0: 2, lift: 34, d: 0 },
  { id: "closure", z0: 4, lift: 68, d: 0.12 },
  { id: "chain", z0: 6, lift: 102, d: 0.24 },
  { id: "alert", z0: 8, lift: 136, d: 0.36 },
] as const;

const INSET = 6;
const SHEET: P3[] = [[INSET, INSET], [W - INSET, INSET], [W - INSET, D - INSET], [INSET, D - INSET]];
const PINS: P3[] = [[14, 14], [W - 14, 14], [W - 14, D - 14], [14, D - 14]];

function Pin({ at, h }: { at: P3; h: number }) {
  const [x, y] = pr(at);
  return (
    <g className="ml-pin">
      <line x1={x} y1={y} x2={x} y2={y - h} />
      <ellipse cx={x} cy={y} rx={3.4} ry={1.9} className="ml-pin-foot" />
      <circle cx={x} cy={y - h} r={1.6} className="ml-pin-top" />
    </g>
  );
}

function Marker({ at, k }: { at: P3; k: string }) {
  const [x, y] = pr(at);
  return (
    <g className="ml-mk" data-k={k}>
      <ellipse cx={x} cy={y} rx={6} ry={3.2} className="ml-mk-halo" />
      <circle cx={x} cy={y - 1} r={4} />
    </g>
  );
}

function SheetContent({ id }: { id: string }) {
  if (id === "incident")
    return (
      <>
        <Marker at={onHwy(0.18)} k="incident" />
        <Marker at={onHwy(0.47)} k="incident" />
        <Marker at={[92, 110]} k="incident" />
      </>
    );
  if (id === "closure")
    return (
      <>
        <path className="ml-run" data-k="closure" d={path(seg(0.56, 0.66))} />
        <path className="ml-run ml-run-dash" data-k="closure" d={path([[250, 200], [250, 150]])} />
      </>
    );
  if (id === "chain")
    return (
      <>
        <path className="ml-run" data-k="chain" d={path(seg(0.74, 0.92))} />
        <g className="ml-station" data-k="weather">
          {(() => {
            const [x, y] = pr(onHwy(0.84));
            return <rect x={x - 3.5} y={y - 12} width={7} height={7} rx={1.5} />;
          })()}
        </g>
      </>
    );
  return (
    <>
      <path className="ml-area" data-k="weather" d={curve([[262, 10], [380, 14], [392, 120], [330, 150], [262, 92], [262, 10]])} />
      <path className="ml-area" data-k="fire" d={curve([[30, 30], [70, 18], [96, 52], [62, 76], [30, 62], [30, 30]])} />
      <Marker at={[60, 46]} k="fire" />
    </>
  );
}

export default function MapLayers({ n = 1 }: { n?: number | string }) {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const inView = useInView(root, "0px 0px -10% 0px");
  const play = inView && !reduced;

  const corners = [pr([0, 0]), pr([W, 0]), pr([W, D]), pr([0, D])];
  const xs = corners.map((c) => c[0]);
  const TOPSHEET = SHEETS[SHEETS.length - 1];
  const PIN_H = TOPSHEET.z0 + TOPSHEET.lift + 10;
  const top = pr([0, 0, PIN_H])[1];
  const vb = [Math.min(...xs) - 14, top - 30, Math.max(...xs) - Math.min(...xs) + 28, pr([W, D])[1] + T + 22 - (top - 30)];

  return (
    <FigureFrame
      n={n}
      title="Many feeds, one map"
      className="csf-layers"
      legend={
        <ul className="csf-keys">
          <li className="csf-key"><span className="csf-sw ml-sw" data-k="incident" /> Crashes and incidents</li>
          <li className="csf-key"><span className="csf-sw ml-sw" data-k="closure" /> Closures and roadwork</li>
          <li className="csf-key"><span className="csf-sw ml-sw" data-k="chain" /> Chain controls</li>
          <li className="csf-key"><span className="csf-sw ml-sw" data-k="weather" /> Road weather and alerts</li>
          <li className="csf-key"><span className="csf-sw ml-sw" data-k="fire" /> Wildfires</li>
        </ul>
      }
      caption={
        <>
          Each agency publishes one kind of information. CommuteScout treats each as a layer and lines them up on the same
          base map, so a crash, a chain control and a storm warning land on the same road. A sample map.
        </>
      }
    >
      <div ref={root} className="ml" data-play={play ? "" : undefined}>
        <svg className="csf-svg ml-svg" viewBox={vb.map((v) => v.toFixed(0)).join(" ")} role="img" aria-label="Four clear map sheets, one per kind of feed, lowering onto a base map so all the markers line up on the same roads.">
          {/* table body */}
          <polygon className="ml-side ml-side-l" points={pts([[0, D], [W, D], [W, D, -T], [0, D, -T]])} />
          <polygon className="ml-side ml-side-r" points={pts([[W, 0], [W, D], [W, D, -T], [W, 0, -T]])} />
          <path className="ml-edge" d={path([[0, D, -T], [W, D, -T], [W, 0, -T]])} />
          <path className="ml-edge" d={path([[W, D], [W, D, -T]])} />
          {[0.25, 0.5, 0.75].map((u) => {
            const [x, y] = pr([W * u, D, -T / 2]);
            return <circle key={u} className="ml-screw" cx={x} cy={y} r={0.9} />;
          })}
          {/* light table glass with the base map */}
          <polygon className="ml-top" points={pts([[0, 0], [W, 0], [W, D], [0, D]])} />
          <polygon className="ml-glow" points={pts([[10, 10], [W - 10, 10], [W - 10, D - 10], [10, D - 10]])} />
          <path className="ml-water" d={curve(RIVER)} />
          <path className="ml-lake" d={curve([...LAKE, LAKE[0]])} />
          {ROADS.map((r, i) => (
            <g key={i}>
              <path className="ml-road-case" d={curve(r)} />
              <path className="ml-road" d={curve(r)} />
            </g>
          ))}
          <path className="ml-hwy-case" d={curve(HWY)} />
          <path className="ml-hwy" d={curve(HWY)} />
          {TOWNS.map((t, i) => {
            const [x, y] = pr(t);
            return <circle key={i} className="ml-town" cx={x} cy={y} r={2.6} />;
          })}
          {PINS.map((p, i) => (
            <Pin key={i} at={p} h={PIN_H} />
          ))}
          {/* the sheets, bottom to top */}
          {SHEETS.map((s) => (
            <g
              key={s.id}
              className="ml-sheet"
              data-k={s.id}
              style={{ ["--up" as string]: `${-s.lift}px`, ["--d" as string]: `${s.d}s` } as React.CSSProperties}
            >
              {/* the glass sits a hair above the one below; the ink is printed on its underside,
                  so when the sheets are down every marker lands exactly on the base map */}
              <g transform={`translate(0 ${-s.z0})`}>
                <polygon className="ml-glass" points={pts(SHEET)} />
                <path className="ml-glass-edge" d={path([[INSET, D - INSET], [W - INSET, D - INSET], [W - INSET, INSET]])} />
                {PINS.map((p, i) => {
                  const [x, y] = pr(p);
                  return <circle key={i} className="ml-hole" cx={x} cy={y} r={2.4} />;
                })}
              </g>
              <SheetContent id={s.id} />
            </g>
          ))}
        </svg>
      </div>
    </FigureFrame>
  );
}
