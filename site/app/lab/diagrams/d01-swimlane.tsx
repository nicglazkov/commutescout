"use client";

import { useMemo } from "react";
import { FigureFrame } from "@/components/figures/frame";
import { FEEDS, LOOP, STILL, clock, sayAt, stateAt, type State } from "./sim";
import { useClock, usePlay } from "./use-play";

// 1. Pipeline swimlane. Every stage and number is read off the code:
//    feeds and their refresh and keep times (ca_roads/feeds/*.py, ca_roads_demo/states.py),
//    the combine step (app.build_markers), the three published bundles (snapshot.BUNDLES)
//    and the map's 30 s check (static/map-app.js). The motion runs the model in sim.ts.

const SPEED = 4;
type Lane = { src: string; fmt: string; read: string; readSub: string; keep: string; keepSub: string; to: number };
// same order as FEEDS
const LANES: Lane[] = [
  { src: "Highway patrol", fmt: "XML · incidents", read: "60 s", readSub: "asks “changed?”", keep: "10 min", keepSub: "then dropped", to: 0 },
  { src: "State DOT closures", fmt: "XML · 12 districts", read: "5 min", readSub: "all at once", keep: "30 min", keepSub: "then dropped", to: 0 },
  { src: "Other states' DOTs", fmt: "JSON · XML · WZDx", read: "3 min", readSub: "60 s fetch cap", keep: "30 min", keepSub: "then dropped", to: 0 },
  { src: "National fire service", fmt: "ArcGIS JSON", read: "5 min", readSub: "with outlines", keep: "60 min", keepSub: "then dropped", to: 0 },
  { src: "Signs, road weather", fmt: "XML · JSON", read: "2.5 min", readSub: "all districts", keep: "30 min", keepSub: "then dropped", to: 1 },
  { src: "Camera lists", fmt: "inventories", read: "2.5–10 min", readSub: "list only", keep: "6 hours", keepSub: "an inventory", to: 2 },
];
const BUNDLES = [
  { name: "live.json.gz", every: "every 30 s", what: "incidents, closures, chains, fires, tolls" },
  { name: "signs.json.gz", every: "every 5 min", what: "signs, road weather" },
  { name: "cameras.json.gz", every: "every hour", what: "camera lists" },
];

const X = { src: 0, read: 176, keep: 304, comb: 412, pub: 520, dev: 686 };
const W = { src: 160, read: 112, keep: 92, comb: 92, pub: 150, dev: 134 };
const Y0 = 50;
const LH = 56;
const BH = 44;
const laneY = (i: number) => Y0 + i * LH;
const BOT = laneY(LANES.length) - (LH - BH);
const LIVE_H = 132;
const bundleY = (j: number) => {
  const h = j === 0 ? LIVE_H : (BOT - Y0 - LIVE_H - 2 * 12) / 2;
  const y = j === 0 ? Y0 : Y0 + LIVE_H + 12 + (j - 1) * (h + 12);
  return { y, h };
};
const EDGE = { y: Y0, h: 88 };
const MAP = { y: Y0 + 88 + 24, h: BOT - Y0 - 88 - 24 };

function Arrow({ x, y }: { x: number; y: number }) {
  return <path className="arrow" d={`M${x} ${y}l-6 -3.5v7z`} />;
}

// The copy's age against its refresh time, as a bar inside the read box.
function AgeBar({ st, i, x, y, w }: { st: State; i: number; x: number; y: number; w: number }) {
  const f = Math.min(1, st.age[i] / FEEDS[i].ttl);
  const stale = st.fetching[i] !== null;
  return (
    <g>
      <rect className="track" x={x} y={y} width={w} height={4} rx={2} />
      <rect className={stale ? "fill-stale" : "fill-k"} x={x} y={y} width={Math.max(4, w * f)} height={4} rx={2} />
    </g>
  );
}

function Desk({ st, play }: { st: State; play: boolean }) {
  const s = st.s;
  const b = st.build;
  const since = b ? s - b.t : 99;
  const c = st.check;
  const sinceCheck = c ? s - c.t : 99;
  const upload = b?.changed ?? false;
  const liveY = bundleY(0).y + 30;
  // a changed build travels combine -> live.json.gz; the map's check brings it on
  const packet = play && upload && since < 4 ? X.comb + W.comb + ((X.pub - X.comb - W.comb) * since) / 4 : null;
  // the map's check: down from the edge cache to the map
  const checkY = play && c && sinceCheck < 3 ? EDGE.y + EDGE.h + ((MAP.y - EDGE.y - EDGE.h) * sinceCheck) / 3 : null;
  return (
    <svg className="csf-svg" viewBox="0 0 820 436" role="img" aria-label="Swimlane: six kinds of source, each re-read once its copy is older than its refresh time and kept in memory up to its keep time. Every 30 seconds one build combines them into one list, published as three files and read by the map every 30 seconds through the edge cache. The REST API and MCP read the held copies directly.">
      {(
        [
          ["Source", X.src],
          ["Re-read after", X.read],
          ["Kept for", X.keep],
          ["Every 30 s", X.comb],
          ["Published", X.pub],
          ["Read by", X.dev],
        ] as const
      ).map(([l, x]) => (
        <text key={l} className="t-head" x={x} y={22}>{l}</text>
      ))}
      <line className="rule" x1={0} x2={820} y1={34} y2={34} />

      {LANES.map((l, i) => {
        const y = laneY(i);
        const cy = y + BH / 2;
        const bb = bundleY(l.to);
        const by = bb.y + Math.min(bb.h / 2, 30);
        const p = st.fetching[i];
        return (
          <g key={l.src} data-k={FEEDS[i].k}>
            <rect className="box" x={X.src} y={y} width={W.src} height={BH} rx={7} />
            <rect className="bar-k" x={X.src} y={y + 8} width={3} height={BH - 16} rx={1.5} />
            <text className="t-strong t-l" x={X.src + 13} y={y + 19}>{l.src}</text>
            <text className="t-mono t-m" x={X.src + 13} y={y + 35}>{l.fmt}</text>

            <path className="wire" d={`M${X.src + W.src} ${cy}H${X.read}`} />
            <Arrow x={X.read} y={cy} />
            <rect className={p !== null && play ? "box-k" : "box-2"} x={X.read} y={y} width={W.read} height={BH} rx={7} />
            <text className="t-mono-ink t-v" x={X.read + 10} y={y + 17}>{l.read}</text>
            <text className="t-s" x={X.read + 10} y={y + 31}>{l.readSub}</text>
            <AgeBar st={st} i={i} x={X.read + 10} y={y + 36} w={W.read - 20} />
            {play && p !== null && <circle className="dot-k" r={3.5} cx={X.src + W.src + (X.read - X.src - W.src) * p} cy={cy} />}

            <path className="wire" d={`M${X.read + W.read} ${cy}H${X.keep}`} />
            <Arrow x={X.keep} y={cy} />
            <rect className="box-2" x={X.keep} y={y} width={W.keep} height={BH} rx={7} />
            <text className="t-mono-ink t-v" x={X.keep + 10} y={y + 19}>{l.keep}</text>
            <text className="t-s" x={X.keep + 10} y={y + 35}>{l.keepSub}</text>

            <path className="wire" d={`M${X.keep + W.keep} ${cy}H${X.comb}`} />
            <Arrow x={X.comb} y={cy} />
            <path className="wire-k" d={`M${X.comb + W.comb} ${cy}C${X.comb + W.comb + 10} ${cy} ${X.pub - 10} ${by} ${X.pub} ${by}`} opacity={0.5} />
          </g>
        );
      })}

      {/* combine, every 30 s */}
      <g data-k="accent">
        <rect className={play && since < 3 ? "box-k" : "box"} x={X.comb} y={Y0} width={W.comb} height={BOT - Y0} rx={9} />
        <text className="t-strong t-l" x={X.comb + 10} y={Y0 + 26}>One list</text>
        {["of markers,", "same fields", "for every", "agency"].map((t, k) => (
          <text key={t} className="t-b" x={X.comb + 10} y={Y0 + 46 + k * 17}>{t}</text>
        ))}
        {["Closures:", "one marker", "per stretch"].map((t, k) => (
          <text key={t} className="t-s" x={X.comb + 10} y={BOT - 48 + k * 15}>{t}</text>
        ))}
      </g>

      {/* the three files */}
      {BUNDLES.map((bu, j) => {
        const { y, h } = bundleY(j);
        return (
          <g key={bu.name} data-k="accent">
            <rect className={j === 0 ? "box-k" : "box"} x={X.pub} y={y} width={W.pub} height={h} rx={7} />
            <text className="t-mono-ink t-v" x={X.pub + 10} y={y + 20}>{bu.name}</text>
            <text className="t-strong t-b" x={X.pub + 10} y={y + 38}>{bu.every}</text>
            {j === 0 ? (
              <>
                {["incidents, closures,", "chains, fires, tolls"].map((t, k) => (
                  <text key={t} className="t-s" x={X.pub + 10} y={y + 58 + k * 15}>{t}</text>
                ))}
                <line className="rule-k" x1={X.pub + 10} x2={X.pub + W.pub - 10} y1={y + 92} y2={y + 92} />
                <text className="t-mono-ink t-m" x={X.pub + 10} y={y + 110}>{b ? clock(b.t) : "—"} build</text>
                <text className={upload ? "t-k t-m" : "t-mono t-m"} x={X.pub + 10} y={y + 124}>{upload ? "changed: uploaded" : "same: not uploaded"}</text>
              </>
            ) : (
              <text className="t-s" x={X.pub + 10} y={y + h - 12}>{bu.what}</text>
            )}
          </g>
        );
      })}
      {packet !== null && <circle className="packet" r={4} cx={packet} cy={liveY} />}

      {/* every file goes out through the edge cache; the map checks it */}
      <path className="wire" d={`M${X.pub + W.pub} ${liveY}H${X.dev}`} />
      <Arrow x={X.dev} y={liveY} />
      {[1, 2].map((j) => {
        const { y, h } = bundleY(j);
        const ey = EDGE.y + 52 + j * 12;
        return <path key={j} className="wire" d={`M${X.pub + W.pub} ${y + h / 2}C${X.dev - 8} ${y + h / 2} ${X.dev - 10} ${ey} ${X.dev} ${ey}`} />;
      })}
      <rect className="box-2" x={X.dev} y={EDGE.y} width={W.dev} height={EDGE.h} rx={9} />
      <text className="t-strong t-b" x={X.dev + 12} y={EDGE.y + 22}>Edge cache</text>
      {["between the files", "and every map;", "holds each 15 s"].map((t, k) => (
        <text key={t} className="t-s" x={X.dev + 12} y={EDGE.y + 41 + k * 15}>{t}</text>
      ))}
      <path className="wire" d={`M${X.dev + W.dev / 2} ${EDGE.y + EDGE.h}V${MAP.y}`} />
      <path className="arrow" d={`M${X.dev + W.dev / 2} ${MAP.y}l-3.5 -6h7z`} />
      {checkY !== null && <circle className={c?.ok200 ? "packet" : "packet-dim"} r={3.5} cx={X.dev + W.dev / 2} cy={checkY} />}
      <g data-k={c?.ok200 ? "incident" : "ok"}>
        <rect className="box" x={X.dev} y={MAP.y} width={W.dev} height={MAP.h} rx={9} />
        <text className="t-strong t-l" x={X.dev + 12} y={MAP.y + 26}>The map</text>
        {["checks the edge", "every 30 s, with", "an ETag"].map((t, k) => (
          <text key={t} className="t-b" x={X.dev + 12} y={MAP.y + 46 + k * 17}>{t}</text>
        ))}
        <line className="rule" x1={X.dev + 12} x2={X.dev + W.dev - 12} y1={MAP.y + MAP.h - 52} y2={MAP.y + MAP.h - 52} />
        <text className="t-mono-ink t-m" x={X.dev + 12} y={MAP.y + MAP.h - 32}>{c ? clock(c.t) : "—"} check</text>
        <text className={c?.ok200 ? "t-k t-m" : "t-mono t-m"} x={X.dev + 12} y={MAP.y + MAP.h - 16}>{c?.ok200 ? "200: new markers" : "304: nothing new"}</text>
      </g>

      {/* API and MCP read the held copies directly */}
      <path className="wire-dash" d={`M${X.keep + W.keep / 2} ${BOT}V${BOT + 42}H${X.comb}`} />
      <Arrow x={X.comb} y={BOT + 42} />
      <rect className="box" x={X.comb} y={BOT + 18} width={X.dev + W.dev - X.comb} height={48} rx={8} />
      <text className="t-strong t-l" x={X.comb + 12} y={BOT + 38}>REST API and MCP server</text>
      <text className="t-mono t-m" x={X.comb + 12} y={BOT + 55}>answer from the held copies · data_as_of on each</text>
      <rect className="box-2" x={X.src} y={BOT + 18} width={X.keep - 24} height={48} rx={8} />
      <text className="t-strong t-l" x={X.src + 13} y={BOT + 38}>Asked live, per place</text>
      <text className="t-mono t-m" x={X.src + 13} y={BOT + 55}>weather alerts, forecasts, speeds</text>
      <path className="wire-dash" d={`M${X.keep - 24} ${BOT + 42}H${X.comb - 8}`} />
    </svg>
  );
}

function Phone({ st }: { st: State }) {
  const b = st.build;
  const c = st.check;
  return (
    <ol className="dg-pipe">
      <li>
        <h3 className="dg-pipe-h"><span>1</span>Read each source on its own</h3>
        <p className="dg-pipe-p">A copy is re-read once it is older than its refresh time, and dropped after its keep time. The bar is the copy&apos;s age.</p>
        <ul className="dg-lanes">
          {LANES.map((l, i) => {
            const f = Math.min(1, st.age[i] / FEEDS[i].ttl);
            return (
              <li key={l.src} data-k={FEEDS[i].k}>
                <span className="dg-lane-name">{l.src}</span>
                <span className="dg-lane-num">re-read after {l.read} · kept {l.keep}</span>
                <span className="dg-lane-bar" aria-hidden="true">
                  <i style={{ width: `${Math.max(4, f * 100)}%` }} data-stale={st.fetching[i] !== null ? "" : undefined} />
                </span>
              </li>
            );
          })}
        </ul>
      </li>
      <li>
        <h3 className="dg-pipe-h"><span>2</span>Combine every 30 s</h3>
        <p className="dg-pipe-p">One list of markers with the same fields for every agency. Closures become one marker per stretch.</p>
      </li>
      <li>
        <h3 className="dg-pipe-h"><span>3</span>Publish three files</h3>
        <dl className="dg-files">
          {BUNDLES.map((bu) => (
            <div key={bu.name}>
              <dt>{bu.name}</dt>
              <dd>{bu.every} · {bu.what}</dd>
            </div>
          ))}
        </dl>
        <p className="dg-pipe-p dg-live-line">
          {b ? clock(b.t) : "—"} build · <b data-on={b?.changed ? "" : undefined}>{b?.changed ? "changed: uploaded" : "same: not uploaded"}</b>
        </p>
      </li>
      <li>
        <h3 className="dg-pipe-h"><span>4</span>Deliver</h3>
        <p className="dg-pipe-p">The map checks the edge cache every 30 s and gets a 304 when nothing changed. The REST API and MCP server answer from the held copies, with <code>data_as_of</code> on every answer.</p>
        <p className="dg-pipe-p dg-live-line">
          {c ? clock(c.t) : "—"} map check · <b data-on={c?.ok200 ? "" : undefined}>{c?.ok200 ? "200: new markers" : "304: nothing new"}</b>
        </p>
      </li>
    </ol>
  );
}

export default function D01Swimlane() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const s = useClock(play, SPEED, STILL, LOOP);
  const st = useMemo(() => stateAt(s), [s]);
  return (
    <FigureFrame
      n={1}
      title="From agency feed to your screen"
      hint={`Each row is a kind of source; the bar is its copy's age · ${SPEED}× speed`}
      readout={sayAt(st)}
      caption={
        <>
          Each source is read on its own and translated into the same marker format. A copy younger than its refresh
          time is served as it is; the first read after that serves it once more while a new copy is fetched behind
          it, and a copy past its keep time is dropped. Every 30 seconds one build combines the copies into one list and
          uploads <code>live.json.gz</code> only if something changed; a build that is missing feeds, or has far fewer markers than the last, is held back. The REST API
          and the MCP server read the same copies directly, and every answer carries its <code>data_as_of</code>.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <div className="csf-desk">
          <Desk st={st} play={play} />
        </div>
        <div className="csf-phone">
          <Phone st={st} />
        </div>
      </div>
    </FigureFrame>
  );
}
