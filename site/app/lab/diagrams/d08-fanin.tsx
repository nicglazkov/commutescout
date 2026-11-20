"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay } from "./use-play";

// 8. Fan-in network: all 53 counted sources as dots, grouped the way the code registers them
// (ca_roads_demo/states.py source_status + the 7 core feeds of the deepest state; WZDx feeds
// superseded by a keyed feed in production are not counted, which is how 53 is reached).
// 7 + 12 + 9 + 1 + 16 + 3 + 5 = 53.

const GROUPS = [
  { label: "One state's full set", sub: "seven kinds of feed", n: 7, k: "incident" },
  { label: "State APIs (with a key)", sub: "one per state, every kind it has", n: 12, k: "closure" },
  { label: "State feeds (no key)", sub: "one per state", n: 9, k: "chain" },
  { label: "National wildfire service", sub: "every state", n: 1, k: "fire" },
  { label: "Work-zone feeds (WZDx)", sub: "roadwork only", n: 16, k: "weather" },
  { label: "Shared regional portal", sub: "three states, one XML", n: 3, k: "neutral" },
  { label: "Toll prices", sub: "posted and dynamic", n: 5, k: "accent" },
];
const PER_ROW = 8;
const DX = 13;
const DOT_X = 200;
const HUB = { x: 470, y: 200 };

type Dot = { x: number; y: number; k: string; g: number };

function layout() {
  const dots: Dot[] = [];
  const heads: { y: number; h: number }[] = [];
  let y = 36;
  GROUPS.forEach((g, gi) => {
    const rows = Math.ceil(g.n / PER_ROW);
    const h = Math.max(30, rows * DX + 14);
    heads.push({ y, h });
    for (let i = 0; i < g.n; i++) {
      dots.push({ x: DOT_X + (i % PER_ROW) * DX, y: y + 8 + Math.floor(i / PER_ROW) * DX, k: g.k, g: gi });
    }
    y += h + 6;
  });
  return { dots, heads, bottom: y };
}

const OUTS = [
  { label: "live.json.gz", sub: "every 30 s", y: 82, k: "accent" },
  { label: "signs.json.gz", sub: "every 5 min", y: 130, k: "neutral" },
  { label: "cameras.json.gz", sub: "every hour", y: 178, k: "neutral" },
  { label: "REST API", sub: "on request", y: 262, k: "neutral" },
  { label: "MCP server", sub: "18 tools, on request", y: 310, k: "neutral" },
];

export default function D08FanIn() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const { dots, heads, bottom } = layout();
  const H = bottom + 64;
  const hubY = Math.min(HUB.y, H / 2);
  return (
    <FigureFrame
      n={8}
      title="53 sources in, one map out"
      hint="Every dot is one counted source"
      readout="53 sources · 37 states"
      caption={
        <>
          Each dot is one source CommuteScout reads, grouped by how it is published. All of them are translated into one
          marker format and held in memory; one build combines them for the map&apos;s three files, and the REST API and
          MCP server answer from the same copies. Weather alerts, forecasts, earthquakes and traffic speeds are asked
          live per place, so they are not in the 53.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <svg className="csf-svg" viewBox={`0 0 720 ${H}`} role="img" aria-label="Fan-in: 53 dots in seven groups (7 from one state's full set, 12 state APIs, 9 keyless state feeds, 1 national wildfire service, 16 work-zone feeds, 3 from a shared regional portal, 5 toll price feeds) all converge on one combine step, which fans out to three published files, the REST API and the MCP server.">
          {/* lines in */}
          {dots.map((d, i) => (
            <path key={i} className="wire" opacity={0.55} d={`M${d.x + 4} ${d.y}C${(d.x + HUB.x) / 2 + 40} ${d.y} ${HUB.x - 90} ${hubY} ${HUB.x - 40} ${hubY}`} />
          ))}
          {/* groups */}
          {GROUPS.map((g, gi) => (
            <g key={g.label} data-k={g.k}>
              <text className="t-strong" x={DOT_X - 16} y={heads[gi].y + 11} textAnchor="end">
                {g.label} <tspan className="t-mono-ink">{g.n}</tspan>
              </text>
              <text className="t-mono" x={DOT_X - 16} y={heads[gi].y + 24} textAnchor="end">{g.sub}</text>
            </g>
          ))}
          {dots.map((d, i) => (
            <g key={i} data-k={d.k}>
              <circle className="dot-k" cx={d.x} cy={d.y} r={4} />
            </g>
          ))}
          {/* hub */}
          <g data-k="accent">
            <circle cx={HUB.x} cy={hubY} r={40} fill="var(--f-bg)" stroke="var(--f-accent)" strokeWidth={1.5} />
            <text className="t-strong" x={HUB.x} y={hubY - 3} textAnchor="middle">one list</text>
            <text className="t-mono" x={HUB.x} y={hubY + 11} textAnchor="middle">same fields</text>
          </g>
          {/* outs */}
          {OUTS.map((o) => (
            <g key={o.label} data-k={o.k}>
              <path className={o.k === "accent" ? "wire-k" : "wire"} d={`M${HUB.x + 40} ${hubY}C${HUB.x + 80} ${hubY} ${560 - 50} ${o.y} ${560} ${o.y}`} />
              <rect className={o.k === "accent" ? "box-k" : "box"} x={560} y={o.y - 18} width={150} height={36} rx={6} />
              <text className="t-strong" x={572} y={o.y - 2}>{o.label}</text>
              <text className="t-mono" x={572} y={o.y + 11}>{o.sub}</text>
            </g>
          ))}
          <text className="t-head" x={560} y={56}>To the map</text>
          <text className="t-head" x={560} y={236}>To assistants and code</text>
          {/* asked live */}
          <g>
            <rect className="box-2" x={DOT_X - 190} y={bottom + 8} width={420} height={36} rx={6} />
            <text className="t-strong" x={DOT_X - 178} y={bottom + 24}>Asked live, per place</text>
            <text className="t-mono" x={DOT_X - 178} y={bottom + 37}>weather alerts · forecasts · earthquakes · traffic speed</text>
            <path className="wire-dash" d={`M${DOT_X + 230} ${bottom + 26}H${520}V${310}H${556}`} />
          </g>
          {play &&
            GROUPS.map((g, gi) => {
              const d = dots.find((x) => x.g === gi)!;
              return (
                <circle key={g.label} className="packet" r={2.6}>
                  <animateMotion dur="4s" begin={`${gi * 0.55}s`} repeatCount="indefinite" path={`M${d.x + 4} ${d.y}C${(d.x + HUB.x) / 2 + 40} ${d.y} ${HUB.x - 90} ${hubY} ${HUB.x - 40} ${hubY}`} />
                </circle>
              );
            })}
        </svg>
      </div>
    </FigureFrame>
  );
}
