"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay } from "./use-play";

// 5. Isometric system drawing (anatomy convention: iso camera at 30 degrees, four-tone faces,
// painter's order back to front, leader-line labels). It draws the real parts: agency
// servers, the app that reads and holds every feed, the file storage behind the edge
// cache holding the three published files, the map in a browser, and an assistant or
// script calling the REST API / MCP server on the same app.

// fixed constants (not Math.cos) so server and client render identical numbers
const C = 0.8660254;
const S = 0.5;
type P3 = [number, number, number?];
const r2 = (v: number) => Math.round(v * 100) / 100;
const pr = ([x, y, z = 0]: P3): [number, number] => [r2((x - y) * C), r2((x + y) * S - z)];
const pts = (a: P3[]) => a.map((p) => pr(p).map((v) => v.toFixed(1)).join(",")).join(" ");
// ground position for a wanted screen point (z = 0)
const at = (sx: number, sy: number): [number, number] => [(sx / C + sy / S) / 2, (sy / S - sx / C) / 2];

function Block({ c, w, d, h, z = 0, k, top }: { c: [number, number]; w: number; d: number; h: number; z?: number; k?: string; top?: string }) {
  const x = c[0] - w / 2;
  const y = c[1] - d / 2;
  return (
    <g data-k={k}>
      <polygon className="iso-l" points={pts([[x, y + d, z], [x + w, y + d, z], [x + w, y + d, z + h], [x, y + d, z + h]])} />
      <polygon className="iso-r" points={pts([[x + w, y, z], [x + w, y + d, z], [x + w, y + d, z + h], [x + w, y, z + h]])} />
      <polygon className={top ?? "iso-top"} points={pts([[x, y, z + h], [x + w, y, z + h], [x + w, y + d, z + h], [x, y + d, z + h]])} />
    </g>
  );
}

function Label({ from, to, lines, anchor = "start" }: { from: [number, number]; to: [number, number]; lines: string[]; anchor?: "start" | "end" }) {
  return (
    <g>
      <circle className="lead-dot" cx={from[0]} cy={from[1]} r={1.8} />
      <path className="lead" d={`M${from[0]} ${from[1]}L${to[0]} ${to[1]}`} />
      {lines.map((l, i) => (
        <text key={i} x={to[0] + (anchor === "start" ? 4 : -4)} y={to[1] + 4 + i * 13} textAnchor={anchor} className={i === 0 ? "t-strong" : "t-small"}>
          {l}
        </text>
      ))}
    </g>
  );
}

const AGENCIES = [
  { k: "incident", name: "Highway patrol", h: 34 },
  { k: "closure", name: "State DOTs", h: 44 },
  { k: "chain", name: "Regional portal", h: 30 },
  { k: "neutral", name: "Work-zone feeds", h: 38 },
  { k: "fire", name: "National fire service", h: 28 },
];
const AG_POS = AGENCIES.map((_, i) => at(-262, -56 + i * 44));
const APP = at(-40, 44);
const STORE = at(150, 4);
const MAP = at(318, -54);
const BOT = at(306, 122);

export default function D05Iso() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const [ax, ay] = pr([...APP]);
  const [sx, sy] = pr([...STORE]);
  const [mx, my] = pr([...MAP]);
  const [bx, by] = pr([...BOT]);
  const feedPaths = AG_POS.map((p) => {
    const [x0, y0] = pr([p[0], p[1]]);
    return `M${(x0 + 14).toFixed(1)} ${y0.toFixed(1)}C${(x0 + 90).toFixed(1)} ${y0.toFixed(1)} ${(ax - 110).toFixed(1)} ${ay.toFixed(1)} ${(ax - 50).toFixed(1)} ${ay.toFixed(1)}`;
  });
  const pubPath = `M${(ax + 50).toFixed(1)} ${ay.toFixed(1)}L${(sx - 30).toFixed(1)} ${(sy + 8).toFixed(1)}`;
  const mapPath = `M${(sx + 30).toFixed(1)} ${(sy - 4).toFixed(1)}L${(mx - 30).toFixed(1)} ${(my + 10).toFixed(1)}`;
  const apiPath = `M${(ax + 40).toFixed(1)} ${(ay + 28).toFixed(1)}L${(bx - 30).toFixed(1)} ${(by + 2).toFixed(1)}`;
  return (
    <FigureFrame
      n={5}
      title="The parts, and what moves between them"
      hint="Isometric drawing; solid lines are the 30-second map path"
      readout="agencies → app → storage → map"
      caption={
        <>
          The app reads every agency feed on its own timer and keeps the last good copy of each. Every 30 seconds it
          builds one marker list and writes it to file storage behind an edge cache, so opening the map never waits on
          an agency. Assistants and scripts ask the same app through the REST API or the MCP server.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <svg className="csf-svg" viewBox="-430 -146 870 330" role="img" aria-label="Isometric drawing: five agency servers on the left feed the CommuteScout app in the middle; the app writes three files to storage behind an edge cache; a browser showing the map fetches from the edge; an assistant calls the app's REST API and MCP server directly.">
          {/* wires on the ground */}
          {feedPaths.map((d, i) => (
            <path key={i} className="wire" d={d} />
          ))}
          <path className="wire" d={pubPath} strokeWidth={2} stroke="var(--f-accent)" />
          <path className="wire" d={mapPath} strokeWidth={2} stroke="var(--f-accent)" />
          <path className="wire-dash" d={apiPath} />

          {/* agencies, back to front */}
          {AGENCIES.map((a, i) => (
            <Block key={a.name} c={AG_POS[i]} w={28} d={28} h={a.h} k={a.k} top="iso-top-k" />
          ))}
          {AGENCIES.map((a, i) => {
            const [x, y] = pr([AG_POS[i][0], AG_POS[i][1], a.h]);
            return (
              <text key={a.name} x={x - 30} y={y + 6} textAnchor="end" className="t-small">
                {a.name}
              </text>
            );
          })}

          {/* the app: a server block with its held copies on top */}
          <Block c={APP} w={110} d={110} h={46} />
          {Array.from({ length: 16 }, (_, i) => {
            const gx = APP[0] - 44 + (i % 4) * 24;
            const gy = APP[1] - 44 + Math.floor(i / 4) * 24;
            const k = ["incident", "closure", "chain", "fire", "weather", "neutral"][i % 6];
            return (
              <g key={i} data-k={k}>
                <polygon className="iso-top-k" points={pts([[gx, gy, 46], [gx + 18, gy, 46], [gx + 18, gy + 18, 46], [gx, gy + 18, 46]])} />
              </g>
            );
          })}

          {/* storage with three files */}
          <Block c={STORE} w={70} d={70} h={22} />
          {[0, 1, 2].map((j) => (
            <Block key={j} c={STORE} w={52 - j * 4} d={52 - j * 4} h={5} z={24 + j * 8} k="accent" top={j === 2 ? "iso-top-k" : "iso-top"} />
          ))}

          {/* the browser with the map */}
          {(() => {
            const w = 96;
            const x = MAP[0] - w / 2;
            const y = MAP[1];
            const z = 8;
            const h = 62;
            return (
              <g>
                <Block c={[MAP[0], MAP[1] - 4]} w={30} d={14} h={8} />
                <polygon className="iso-l" points={pts([[x, y + 3, z], [x + w, y + 3, z], [x + w, y + 3, z + h], [x, y + 3, z + h]])} />
                <polygon className="iso-screen" points={pts([[x + 4, y + 3.2, z + 4], [x + w - 4, y + 3.2, z + 4], [x + w - 4, y + 3.2, z + h - 4], [x + 4, y + 3.2, z + h - 4]])} />
                <path stroke="var(--f-screen-ink)" strokeWidth={1.5} fill="none" opacity={0.6} d={(() => {
                  const a = pr([x + 10, y + 3.2, z + 18]);
                  const b = pr([x + 46, y + 3.2, z + 34]);
                  const c = pr([x + 86, y + 3.2, z + 44]);
                  return `M${a[0]} ${a[1]}Q${b[0]} ${b[1] + 8} ${c[0]} ${c[1]}`;
                })()} />
                {[[30, 26, "incident"], [58, 40, "closure"], [74, 46, "chain"]].map(([px, pz, k]) => {
                  const p = pr([x + (px as number), y + 3.2, z + (pz as number)]);
                  return (
                    <g key={k as string} data-k={k as string}>
                      <circle className="dot-k" cx={p[0]} cy={p[1]} r={3} />
                    </g>
                  );
                })}
              </g>
            );
          })()}

          {/* an assistant or script */}
          <Block c={BOT} w={44} d={44} h={16} />
          <Block c={BOT} w={30} d={30} h={4} z={16} k="accent" top="iso-top-k" />

          {/* packets */}
          {play &&
            [...feedPaths.map((d, i) => ({ d, b: i * 0.5, dur: 5 })), { d: pubPath, b: 0, dur: 3 }, { d: mapPath, b: 1.5, dur: 3 }].map((p, i) => (
              <circle key={i} className="packet" r={2.6}>
                <animateMotion dur={`${p.dur}s`} begin={`${p.b}s`} repeatCount="indefinite" path={p.d} />
              </circle>
            ))}

          {/* labels */}
          <Label from={[ax, ay - 70]} to={[ax - 20, -128]} lines={["CommuteScout app", "reads each feed on its timer,", "keeps the last good copy of each"]} />
          <Label from={[sx + 20, sy + 10]} to={[sx + 44, 50]} lines={["File storage + edge cache", "live 30 s · signs 5 min · cameras 1 h"]} />
          <Label from={[mx + 40, my - 50]} to={[mx + 58, -100]} lines={["Your map", "asks every 30 s"]} />
          <Label from={[bx - 10, by + 14]} to={[bx - 40, by + 40]} anchor="end" lines={["Assistant or script", "REST API · MCP, on request"]} />
        </svg>
      </div>
    </FigureFrame>
  );
}
