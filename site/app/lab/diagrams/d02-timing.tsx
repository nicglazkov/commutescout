"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay, useLoop } from "./use-play";

// 2. Timing diagram: ten minutes to scale. Refresh times are the feeds' TTLs
// (chp/tomtom 60 s, portal 150 s, states 180 s, lcs/chains/wildfire/nws/quakes 300 s,
// WZDx and state camera lists 600 s); bundle cadences are snapshot.BUNDLES; the map
// polls every 30 s (map-app.js).

const SPAN = 600; // seconds shown
const X0 = 210;
const X1 = 704;
const sx = (s: number) => X0 + ((X1 - X0) * s) / SPAN;

type Row = { label: string; sub: string; every: number; k: string; shape?: "dot" | "tick" | "file"; offset?: number };
const FEEDS: Row[] = [
  { label: "Highway patrol incidents", sub: "60 s", every: 60, k: "incident", offset: 12 },
  { label: "Traffic speed", sub: "60 s", every: 60, k: "neutral", offset: 40 },
  { label: "Signs, cameras, road weather", sub: "2.5 min", every: 150, k: "weather", offset: 25 },
  { label: "Other states' feeds", sub: "3 min", every: 180, k: "chain", offset: 70 },
  { label: "Closures and chain controls", sub: "5 min", every: 300, k: "closure", offset: 95 },
  { label: "Wildfires, alerts, quakes", sub: "5 min", every: 300, k: "fire", offset: 150 },
  { label: "Work-zone feeds, camera lists", sub: "10 min", every: 600, k: "neutral", offset: 210 },
];
const OUT: Row[] = [
  { label: "live.json.gz published", sub: "30 s", every: 30, k: "accent", shape: "file", offset: 0 },
  { label: "signs.json.gz published", sub: "5 min", every: 300, k: "accent", shape: "file", offset: 0 },
  { label: "cameras.json.gz published", sub: "1 hour", every: 3600, k: "accent", shape: "file", offset: 0 },
  { label: "Your map asks for news", sub: "30 s", every: 30, k: "ok", shape: "dot", offset: 8 },
];

const RH = 22;

function Ticks({ r, y }: { r: Row; y: number }) {
  const out = [];
  for (let s = r.offset ?? 0; s <= SPAN; s += r.every) out.push(s);
  return (
    <g data-k={r.k}>
      {out.map((s) =>
        r.shape === "dot" ? (
          <circle key={s} className="ring-k" cx={sx(s)} cy={y} r={3} />
        ) : r.shape === "file" ? (
          <rect key={s} className="bar-k" x={sx(s) - 2.5} y={y - 6} width={5} height={12} rx={1} />
        ) : (
          <line key={s} className="tick-k" x1={sx(s)} x2={sx(s)} y1={y - 6} y2={y + 6} />
        ),
      )}
    </g>
  );
}

export default function D02Timing() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const t = useLoop(play, 24, 0.48);
  const now = t * SPAN;
  const mm = Math.floor(now / 60);
  const ss = Math.floor(now % 60);
  let y = 44;
  const rows: { r: Row; y: number }[] = [];
  FEEDS.forEach((r) => {
    rows.push({ r, y });
    y += RH;
  });
  const outTop = y + 18;
  y = outTop + 14;
  OUT.forEach((r) => {
    rows.push({ r, y });
    y += RH;
  });
  const axisY = y + 4;
  return (
    <FigureFrame
      n={2}
      title="Who reads what, and when"
      hint="Ten minutes, to scale"
      readout={play ? `t = ${mm}:${String(ss).padStart(2, "0")}` : "0:00 to 10:00"}
      caption={
        <>
          Every source has its own refresh time, set by how fast that kind of information changes. A copy older than
          that is re-read the next time anything asks for it. The live file is rebuilt every 30 seconds, and if no
          marker changed it is not uploaded again, so the map&apos;s 30-second check costs a few bytes.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <svg className="csf-svg" viewBox={`0 0 720 ${axisY + 30}`} role="img" aria-label="Timing diagram over ten minutes: incidents and traffic re-read every minute, signs every 2.5 minutes, other states every 3, closures, chains, wildfires and alerts every 5, work-zone feeds every 10; the live file is published every 30 seconds, signs every 5 minutes, cameras every hour; the map checks every 30 seconds.">
          {Array.from({ length: 11 }, (_, i) => (
            <line key={i} className="grid" x1={sx(i * 60)} x2={sx(i * 60)} y1={30} y2={axisY} />
          ))}
          <text className="t-head" x={0} y={24}>Sources re-read</text>
          <text className="t-head" x={X1} y={24} textAnchor="end">every</text>
          <text className="t-head" x={0} y={outTop}>Published and fetched</text>
          {rows.map(({ r, y: ry }) => (
            <g key={r.label}>
              <text x={0} y={ry + 4} className={r.k === "accent" || r.k === "ok" ? "t-strong" : undefined}>{r.label}</text>
              <text className="t-mono" x={X0 - 12} y={ry + 4} textAnchor="end">{r.sub}</text>
              <line className="rule" x1={X0} x2={X1} y1={ry} y2={ry} />
              <Ticks r={r} y={ry} />
            </g>
          ))}
          {/* the camera file never ticks inside ten minutes */}
          {(() => {
            const cam = rows.find((x) => x.r.label.startsWith("cameras"));
            return cam ? (
              <text className="t-mono" x={sx(30)} y={cam.y + 3.5}>
                next one at 60:00
              </text>
            ) : null;
          })()}
          <line className="rule" x1={X0} x2={X1} y1={axisY} y2={axisY} />
          {Array.from({ length: 11 }, (_, i) => (
            <text key={i} className="t-mono" x={sx(i * 60)} y={axisY + 16} textAnchor="middle">
              {i}:00
            </text>
          ))}
          {/* playhead */}
          {play && (
          <g data-k="accent" transform={`translate(${sx(now).toFixed(1)} 0)`}>
            <line x1={0} x2={0} y1={32} y2={axisY} stroke="var(--f-accent)" strokeWidth={1.2} />
            <path className="arrow-k" d="M-4 30h8l-4 5z" />
          </g>
          )}
        </svg>
      </div>
    </FigureFrame>
  );
}
