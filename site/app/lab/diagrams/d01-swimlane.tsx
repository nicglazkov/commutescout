"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay } from "./use-play";

// 1. Pipeline swimlane. Every stage and number is read off the code:
//    feeds and their cache times (ca_roads/feeds/*.py, ca_roads_demo/states.py TTL/MAX_SERVE),
//    the combine step (app.build_markers), the three published bundles (snapshot.BUNDLES)
//    and the map's 30 s poll (static/map-app.js).

type Lane = { k: string; src: string; fmt: string; read: string; readSub: string; hold: string; holdSub: string; to: number };
const LANES: Lane[] = [
  { k: "incident", src: "Highway patrol", fmt: "XML · incidents", read: "every 60 s", readSub: "only if changed", hold: "fresh 60 s", holdSub: "kept 10 min", to: 0 },
  { k: "closure", src: "State DOT closures", fmt: "XML · one per district", read: "every 5 min", readSub: "all districts", hold: "fresh 5 min", holdSub: "kept 30 min", to: 0 },
  { k: "chain", src: "Other states' DOTs", fmt: "JSON · XML · WZDx", read: "every 3 min", readSub: "60 s cap", hold: "fresh 3 min", holdSub: "kept 30 min", to: 0 },
  { k: "fire", src: "National fire service", fmt: "ArcGIS JSON", read: "every 5 min", readSub: "with outlines", hold: "fresh 5 min", holdSub: "kept 60 min", to: 0 },
  { k: "weather", src: "Signs and road weather", fmt: "XML · JSON", read: "every 2.5 min", readSub: "all districts", hold: "fresh 2.5 min", holdSub: "kept 30 min", to: 1 },
  { k: "neutral", src: "Camera lists", fmt: "inventories", read: "2.5–10 min", readSub: "list only", hold: "kept 6 hours", holdSub: "an inventory", to: 2 },
];

const X = { src: 0, read: 168, hold: 280, comb: 388, pub: 490, dev: 626 };
const W = { src: 150, read: 96, hold: 92, comb: 86, pub: 118, dev: 94 };
const Y0 = 44;
const LH = 50;
const BH = 38;
const laneY = (i: number) => Y0 + i * LH;
const BOT = laneY(LANES.length) - (LH - BH);
const BUNDLES = [
  { name: "live.json.gz", every: "every 30 s", what: ["incidents,", "closures, chains,", "fires, tolls"] },
  { name: "signs.json.gz", every: "every 5 min", what: ["signs,", "road weather"] },
  { name: "cameras.json.gz", every: "every hour", what: ["camera lists"] },
];
const bundleY = (j: number) => {
  const h = (BOT - Y0 - 2 * 10) / 3;
  return { y: Y0 + j * (h + 10), h };
};

function Arrow({ x, y }: { x: number; y: number }) {
  return <path className="arrow" d={`M${x} ${y}l-5 -3v6z`} />;
}

export default function D01Swimlane() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const midY = (Y0 + BOT) / 2;
  return (
    <FigureFrame
      n={1}
      title="From agency feed to your screen"
      hint="Each row is a kind of source, read on its own schedule"
      readout="53 sources · 3 published files · map asks every 30 s"
      caption={
        <>
          Each source is read on its own timer and translated into the same marker format. A copy stays in memory: inside
          its fresh time it is served as is, after that it is served at once while a new copy is fetched behind it, and a
          copy past its keep time is dropped. One build combines every copy into one list, published as three files.
          The REST API and the MCP server read the same copies directly, and every answer carries its <code>data_as_of</code>.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <svg className="csf-svg" viewBox="0 0 720 420" role="img" aria-label="Swimlane: six kinds of source, each read on its own schedule, translated into markers, held in memory, combined into one list, published as three files and read by the map; the REST API and MCP read the held copies directly.">
          {[
            ["Source", X.src],
            ["Read", X.read],
            ["Hold in memory", X.hold],
            ["Combine", X.comb],
            ["Publish", X.pub],
            ["Deliver", X.dev],
          ].map(([l, x]) => (
            <text key={l as string} className="t-head" x={x as number} y={20}>
              {l}
            </text>
          ))}
          <line className="rule" x1={0} x2={720} y1={30} y2={30} />

          {LANES.map((l, i) => {
            const y = laneY(i);
            const cy = y + BH / 2;
            const b = bundleY(l.to);
            const by = b.y + b.h / 2;
            return (
              <g key={l.src} data-k={l.k}>
                <rect className="box" x={X.src} y={y} width={W.src} height={BH} rx={6} />
                <rect className="bar-k" x={X.src} y={y + 6} width={3} height={BH - 12} rx={1.5} />
                <text className="t-strong" x={X.src + 12} y={y + 16}>{l.src}</text>
                <text className="t-mono" x={X.src + 12} y={y + 30}>{l.fmt}</text>

                <path className="wire" d={`M${X.src + W.src} ${cy}H${X.read}`} />
                <Arrow x={X.read} y={cy} />
                <rect className="box-2" x={X.read} y={y} width={W.read} height={BH} rx={6} />
                <text className="t-mono-ink" x={X.read + 8} y={y + 16}>{l.read}</text>
                <text className="t-mono" x={X.read + 8} y={y + 30}>{l.readSub}</text>

                <path className="wire" d={`M${X.read + W.read} ${cy}H${X.hold}`} />
                <Arrow x={X.hold} y={cy} />
                <rect className="box-2" x={X.hold} y={y} width={W.hold} height={BH} rx={6} />
                <text className="t-mono-ink" x={X.hold + 8} y={y + 16}>{l.hold}</text>
                <text className="t-mono" x={X.hold + 8} y={y + 30}>{l.holdSub}</text>

                <path className="wire" d={`M${X.hold + W.hold} ${cy}H${X.comb}`} />
                <Arrow x={X.comb} y={cy} />
                {/* combine to the bundle this kind is published in */}
                <path className="wire-k" d={`M${X.comb + W.comb} ${cy}C${X.comb + W.comb + 6} ${cy} ${X.pub - 8} ${by} ${X.pub} ${by}`} opacity={0.55} />
                {play && (
                  <circle className="dot-k" r={3}>
                    <animateMotion
                      dur="6s"
                      begin={`${(i * 0.45).toFixed(2)}s`}
                      repeatCount="indefinite"
                      path={`M${X.src + W.src} ${cy}H${X.comb}`}
                    />
                  </circle>
                )}
              </g>
            );
          })}

          {/* combine */}
          <rect className="box" x={X.comb} y={Y0} width={W.comb} height={BOT - Y0} rx={8} />
          <text className="t-strong" x={X.comb + 10} y={midY - 30}>One list</text>
          <text className="t-small" x={X.comb + 10} y={midY - 14}>of markers,</text>
          <text className="t-small" x={X.comb + 10} y={midY}>same fields</text>
          <text className="t-small" x={X.comb + 10} y={midY + 14}>for every</text>
          <text className="t-small" x={X.comb + 10} y={midY + 28}>agency</text>
          <text className="t-mono" x={X.comb + 10} y={BOT - 24}>closures:</text>
          <text className="t-mono" x={X.comb + 10} y={BOT - 11}>1 per stretch</text>

          {/* bundles */}
          {BUNDLES.map((b, j) => {
            const { y, h } = bundleY(j);
            return (
              <g key={b.name} data-k="accent">
                <rect className={j === 0 ? "box-k" : "box"} x={X.pub} y={y} width={W.pub} height={h} rx={6} />
                <text className="t-mono-ink" x={X.pub + 8} y={y + 18}>{b.name}</text>
                <text className="t-strong t-small" x={X.pub + 8} y={y + 34}>{b.every}</text>
                {b.what.map((w, wi) => (
                  <text key={w} className="t-mono" x={X.pub + 8} y={y + h - 10 - (b.what.length - 1 - wi) * 12}>
                    {w}
                  </text>
                ))}
                <path className="wire" d={`M${X.pub + W.pub} ${y + h / 2}C${X.dev - 6} ${y + h / 2} ${X.dev - 12} ${midY - 40} ${X.dev} ${midY - 40}`} />
              </g>
            );
          })}

          {/* the map */}
          <g data-k="accent">
            <rect className="box" x={X.dev} y={midY - 90} width={W.dev} height={110} rx={8} />
            <text className="t-strong" x={X.dev + 10} y={midY - 68}>The map</text>
            <text className="t-small" x={X.dev + 10} y={midY - 50}>from the edge</text>
            <text className="t-small" x={X.dev + 10} y={midY - 36}>cache, asks</text>
            <text className="t-small" x={X.dev + 10} y={midY - 22}>every 30 s</text>
            <text className="t-mono" x={X.dev + 10} y={midY + 4}>304 if nothing</text>
            <text className="t-mono" x={X.dev + 10} y={midY + 16}>changed</text>
            {play && (
              <circle className="packet" r={3}>
                <animateMotion dur="6s" repeatCount="indefinite" path={`M${X.comb + W.comb} ${bundleY(0).y + bundleY(0).h / 2}H${X.pub + W.pub}L${X.dev} ${midY - 40}`} />
              </circle>
            )}
          </g>

          {/* API and MCP, beside the publish path */}
          <path className="wire-dash" d={`M${X.hold + W.hold / 2} ${BOT}V${BOT + 34}H${X.comb}`} />
          <Arrow x={X.comb} y={BOT + 34} />
          <rect className="box" x={X.comb} y={BOT + 16} width={X.dev + W.dev - X.comb} height={38} rx={6} />
          <text className="t-strong" x={X.comb + 10} y={BOT + 32}>REST API and MCP server</text>
          <text className="t-mono" x={X.comb + 10} y={BOT + 46}>answer from the held copies · data_as_of on each</text>
          <rect className="box-2" x={X.src} y={BOT + 16} width={W.src + 100} height={38} rx={6} />
          <text className="t-strong" x={X.src + 12} y={BOT + 32}>Asked live, per place</text>
          <text className="t-mono" x={X.src + 12} y={BOT + 46}>weather alerts, forecasts, speeds</text>
          <path className="wire-dash" d={`M${X.src + W.src + 100} ${BOT + 35}H${X.hold - 6}`} />
        </svg>
      </div>
    </FigureFrame>
  );
}
