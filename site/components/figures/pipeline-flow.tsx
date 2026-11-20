"use client";

import { useMemo } from "react";
import { FigureFrame } from "./frame";
import { usePlay, useClock } from "./use-clock";
import { CARRY, FEEDS, HORIZON, STILL, due, sayAt, stateAt, type State } from "./pipeline-sim";
import "./pipeline-flow.css";

// From agency feed to your map. Each row is a kind of source, re-checked on its own refresh
// time; every 30 s the copies are combined into one file; the map downloads it only when it
// changed; the API and assistant read the same copies. Every number and every motion comes from
// the model in pipeline-sim.ts, which is read off the backend code.
//
// Colour means one thing each, keyed in the legend:
//   green bar  = our copy is fresh (its length is the copy's age against its refresh time)
//   purple bar = the copy is due; it is re-checked at the next 30 s combine
//   ink dot    = data moving (a new copy coming in, the copies going into the file, a download)
//   hollow dot = the map checked and there was nothing new
// Structure (boxes, wires, text) stays neutral.

const SPEED = 6;

const X = { src: 0, copy: 250, comb: 490, out: 670 };
const W = { src: 190, copy: 180, comb: 120, out: 130 };
const Y0 = 46;
const LH = 60;
const BH = 46;
const rowY = (i: number) => Y0 + i * LH;
const BOT = rowY(FEEDS.length - 1) + BH;
const OUT_H = LH + BH;
const MAP_CY = Y0 + OUT_H / 2;
const API_Y = rowY(2);
const BAR_W = W.copy - 24;

function Arrow({ x, y, up }: { x: number; y: number; up?: boolean }) {
  return <path className="pfl-arrow" d={up ? `M${x} ${y}l-3.5 6h7z` : `M${x} ${y}l-6 -3.5v7z`} />;
}

function Bar({ st, i, x, y, w }: { st: State; i: number; x: number; y: number; w: number }) {
  const isDue = due(st, i);
  const f = Math.min(1, st.age[i] / FEEDS[i].ttl);
  return (
    <g>
      <rect className="pfl-track" x={x} y={y} width={w} height={6} rx={3} />
      <rect className="pfl-bar" data-due={isDue ? "" : undefined} x={x} y={y} width={Math.max(6, w * f)} height={6} rx={3} />
    </g>
  );
}

function Desk({ st, play }: { st: State; play: boolean }) {
  const s = st.s;
  const carry = st.build ? (s - st.build.t) / CARRY : 1;
  const down = st.check ? (s - st.check.t) / CARRY : 1;
  return (
    <svg
      className="csf-svg pfl-svg"
      viewBox={`0 0 800 ${BOT + 54}`}
      role="img"
      aria-label="Four kinds of agency source, each re-checked on its own schedule: highway patrol after 1 minute, road department closures after 5 minutes, state DOT feeds after 3 minutes, fire services after 5 minutes. Every 30 seconds our copies are combined into one file. Your map checks the file every 30 seconds and downloads it only when it changed. The API and AI assistant read the same copies directly."
    >
      {(
        [
          ["Source", X.src],
          ["Our copy", X.copy],
          ["Every 30 s", X.comb],
          ["Who reads it", X.out],
        ] as const
      ).map(([l, x]) => (
        <text key={l} className="pfl-head" x={x} y={18}>
          {l}
        </text>
      ))}
      <line className="pfl-rule" x1={0} x2={800} y1={30} y2={30} />

      {FEEDS.map((f, i) => {
        const y = rowY(i);
        const cy = y + BH / 2;
        const p = st.fetching[i];
        return (
          <g key={f.k}>
            <rect className="pfl-box" x={X.src} y={y} width={W.src} height={BH} rx={8} />
            <text className="pfl-name" x={X.src + 14} y={y + 20}>
              {f.name}
            </text>
            <text className="pfl-sub" x={X.src + 14} y={y + 36}>
              {f.what}
            </text>

            <path className="pfl-wire" d={`M${X.src + W.src} ${cy}H${X.copy}`} />
            <Arrow x={X.copy} y={cy} />
            {play && p !== null && <circle className="pfl-dot" r={4} cx={X.src + W.src + 4 + (X.copy - X.src - W.src - 10) * p} cy={cy} />}

            <rect className="pfl-box2" x={X.copy} y={y} width={W.copy} height={BH} rx={8} />
            <text className="pfl-sub pfl-ink2" x={X.copy + 12} y={y + 20}>
              re-checked after <tspan className="pfl-num">{f.every}</tspan>
            </text>
            <Bar st={st} i={i} x={X.copy + 12} y={y + 29} w={BAR_W} />

            <path className="pfl-wire" d={`M${X.copy + W.copy} ${cy}H${X.comb}`} />
            <Arrow x={X.comb} y={cy} />
            {play && carry < 1 && <circle className="pfl-dot" r={4} cx={X.copy + W.copy + 4 + (X.comb - X.copy - W.copy - 10) * carry} cy={cy} />}
          </g>
        );
      })}

      <rect className="pfl-box" x={X.comb} y={Y0} width={W.comb} height={BOT - Y0} rx={10} />
      <text className="pfl-name" x={X.comb + 14} y={Y0 + (BOT - Y0) / 2 - 12}>
        Combined
      </text>
      <text className="pfl-sub pfl-ink2" x={X.comb + 14} y={Y0 + (BOT - Y0) / 2 + 6}>
        into one file
      </text>
      <text className="pfl-sub pfl-ink2" x={X.comb + 14} y={Y0 + (BOT - Y0) / 2 + 22}>
        for every map
      </text>

      <path className="pfl-wire" d={`M${X.comb + W.comb} ${MAP_CY}H${X.out}`} />
      <Arrow x={X.out} y={MAP_CY} />
      {play && down < 1 && st.check && (
        <circle className={st.check.got ? "pfl-dot" : "pfl-hollow"} r={4} cx={X.comb + W.comb + 4 + (X.out - X.comb - W.comb - 10) * down} cy={MAP_CY} />
      )}
      <rect className="pfl-box" x={X.out} y={Y0} width={W.out} height={OUT_H} rx={10} />
      <text className="pfl-name" x={X.out + 14} y={Y0 + 24}>
        Your map
      </text>
      {["checks every 30 s,", "downloads the file", "only if it changed"].map((t, k) => (
        <text key={t} className="pfl-sub pfl-ink2" x={X.out + 14} y={Y0 + 46 + k * 17}>
          {t}
        </text>
      ))}

      <rect className="pfl-box" x={X.out} y={API_Y} width={W.out} height={OUT_H} rx={10} />
      <text className="pfl-name" x={X.out + 14} y={API_Y + 24}>
        API, assistant
      </text>
      {["read our copies", "directly; answers", "show their age"].map((t, k) => (
        <text key={t} className="pfl-sub pfl-ink2" x={X.out + 14} y={API_Y + 46 + k * 17}>
          {t}
        </text>
      ))}
      {/* the API and assistant read every held copy, not the file */}
      <path className="pfl-dash" d={`M${X.copy} ${BOT + 8}v6H${X.copy + W.copy}v-6M${X.copy + W.copy / 2} ${BOT + 14}V${BOT + 30}H${X.out + W.out / 2}V${BOT + 6}`} />
      <Arrow x={X.out + W.out / 2} y={BOT} up />
      <text className="pfl-sub" x={X.comb + W.comb / 2} y={BOT + 47} textAnchor="middle">
        the same copies, any time
      </text>
    </svg>
  );
}

function Phone({ st, play }: { st: State; play: boolean }) {
  const check = st.check;
  return (
    <ol className="pfl-steps">
      <li>
        <h3 className="pfl-step-h">
          <span aria-hidden="true">1</span>Each source is checked on its own
        </h3>
        <ul className="pfl-lanes">
          {FEEDS.map((f, i) => {
            const fr = Math.min(1, st.age[i] / f.ttl);
            return (
              <li key={f.k}>
                <span className="pfl-lane-name">{f.name}</span>
                <span className="pfl-lane-what">
                  {f.what} · <span className="pfl-nowrap">re-checked after <b>{f.every}</b></span>
                </span>
                <span className="pfl-lane-bar" aria-hidden="true">
                  <i style={{ width: `${Math.max(4, fr * 100)}%` }} data-due={due(st, i) ? "" : undefined} />
                </span>
                {play && st.fetching[i] !== null && <span className="pfl-lane-note">new copy coming in</span>}
              </li>
            );
          })}
        </ul>
      </li>
      <li>
        <h3 className="pfl-step-h">
          <span aria-hidden="true">2</span>Every 30 s, combined into one file
        </h3>
      </li>
      <li>
        <h3 className="pfl-step-h">
          <span aria-hidden="true">3</span>Your map checks every 30 s
        </h3>
        <p className="pfl-step-p">It downloads the file only when it has changed.</p>
        {check && (
          <p className="pfl-step-p pfl-live" aria-hidden="true">
            <span className={check.got ? "pfl-key-dot" : "pfl-key-hollow"} /> {check.got ? "Downloaded the new file" : "Checked: nothing new"}
          </p>
        )}
      </li>
      <li>
        <h3 className="pfl-step-h">
          <span aria-hidden="true">4</span>The API and assistant read the same copies
        </h3>
        <p className="pfl-step-p">Every answer says how old its data is.</p>
      </li>
    </ol>
  );
}

export default function PipelineFlow({ n = 1 }: { n?: number | string }) {
  const { ref, play } = usePlay<HTMLDivElement>();
  const s = useClock(play, SPEED, STILL, HORIZON);
  const st = useMemo(() => stateAt(s), [s]);
  return (
    <FigureFrame
      n={n}
      title="From agency feed to your map"
      className="csf-pipeline"
      hint={play ? `Running ${SPEED}× faster than real time` : "A still moment; motion is off"}
      readout={<span aria-hidden="true">{sayAt(st)}</span>}
      legend={
        <ul className="csf-keys">
          <li className="csf-key">
            <span className="pfl-key-bar" /> Our copy is fresh; the bar is its age
          </li>
          <li className="csf-key">
            <span className="pfl-key-bar" data-due="" /> Due: re-checked at the next combine
          </li>
          <li className="csf-key">
            <span className="pfl-key-dot" /> Data on the move
          </li>
          <li className="csf-key">
            <span className="pfl-key-hollow" /> Map checked, nothing new
          </li>
        </ul>
      }
      caption={
        <>
          Each source is re-checked on its own schedule. A copy is used until it is due, then refreshed at the next combine,
          which runs every 30 seconds. Your map downloads the combined file only when it has changed, and the API and AI
          assistant read the same copies. If a source stops answering, its last copy stays on the map, marked with its age,
          for 10 minutes to an hour depending on the source. Signs and road weather are combined every 5 minutes, and camera
          lists every hour.
        </>
      }
    >
      <div ref={ref} className="pfl" data-play={play ? "" : undefined}>
        <div className="csf-desk">
          <Desk st={st} play={play} />
        </div>
        <div className="csf-phone">
          <Phone st={st} play={play} />
        </div>
      </div>
    </FigureFrame>
  );
}
