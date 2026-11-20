"use client";

import { memo, useMemo } from "react";
import { FigureFrame } from "@/components/figures/frame";
import { ART } from "./d05-art";
import { BUILD, FEEDS, LOOP, STILL, sayAt, stateAt, type State } from "./sim";
import { along, useClock, usePlay } from "./use-play";

// 5. Isometric system drawing, built with the anatomy kit (app/lab/diagrams/_iso/build.mjs):
// four-tone solids painted back to front on one base plate. Agency servers in a rack, our
// server holding one copy per feed (a blade each, with a gauge of the copy's age against its
// refresh time), storage with the three published files, the edge cache, the map, and a
// laptop calling the API. The live parts run on the pipeline model in sim.ts.

type Pt = readonly number[];
type Desk = typeof ART.desk;
const SPEED = 4;
const API_EVERY = 45;
const lerp = (a: Pt, b: Pt, f: number) => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f] as const;
const gaugeOf = (st: State, i: number) => Math.min(1, st.age[i] / (2 * FEEDS[i].ttl));
const PIN_KINDS = ["closure", "incident", "chain", "fire", "closure"];

const Art = memo(function Art({ html }: { html: string }) {
  return <g dangerouslySetInnerHTML={{ __html: html }} />;
});

function Label({ at, dx = 0, dy, title, sub, align = "start" }: { at: Pt; dx?: number; dy: number; title: string; sub: string; align?: "start" | "end" }) {
  const x = at[0] + dx;
  const y = at[1] + dy;
  const tx = align === "start" ? x + 6 : x - 6;
  const top = dy < 0;
  return (
    <g className="dg-lab">
      <path className="lead" d={`M${at[0]} ${at[1]}L${x} ${top ? y + 16 : y - 18}`} />
      <circle className="lead-dot" cx={at[0]} cy={at[1]} r={2} />
      <text className="t-strong t-lab" x={tx} y={y} textAnchor={align}>{title}</text>
      <text className="t-mono t-lab-sub" x={tx} y={y + 15} textAnchor={align}>{sub}</text>
    </g>
  );
}

function Gauges({ st, gauges, leds, r }: { st: State; gauges: readonly (readonly Pt[])[]; leds: readonly Pt[]; r: number }) {
  return (
    <>
      {gauges.map(([g0, g1], i) => {
        const e = lerp(g0, g1, gaugeOf(st, i));
        return (
          <g key={i} data-k={FEEDS[i].k}>
            <path className="gauge" d={`M${g0[0]} ${g0[1]}L${e[0]} ${e[1]}`} />
            <circle className="led" data-on={st.fetching[i] === null ? "" : undefined} cx={leds[i][0]} cy={leds[i][1]} r={r} />
          </g>
        );
      })}
    </>
  );
}

function RackLeds({ st, leds, r }: { st: State; leds: readonly Pt[]; r: number }) {
  // the rack is drawn bottom up: unit 0 is the last feed
  return (
    <>
      {leds.map((p, u) => {
        const i = FEEDS.length - 1 - u;
        return <circle key={u} data-k={FEEDS[i].k} className="led" data-on={st.fetching[i] !== null ? "" : undefined} cx={p[0]} cy={p[1]} r={r} />;
      })}
    </>
  );
}

function Live({ st, d, packets }: { st: State; d: Desk; packets: boolean }) {
  const s = st.s;
  const b = st.build;
  const sinceBuild = b ? s - b.t : 99;
  const c = st.check;
  const sinceCheck = c ? s - c.t : 99;
  const apiPhase = s % API_EVERY;
  const fresh = st.last200 !== null ? s - st.last200 : 99;
  let check: readonly number[] | null = null;
  if (c && sinceCheck < 4) {
    const f = sinceCheck / 4;
    const out = [...d.paths.toMap].reverse(); // the map asks the edge
    check = c.ok200 ? along([...d.paths.toEdge, ...d.paths.toMap], f) : along(f < 0.5 ? out : d.paths.toMap, (f % 0.5) * 2);
  }
  return (
    <g className="dg-live">
      <RackLeds st={st} leds={d.rack.leds} r={2.3} />
      <Gauges st={st} gauges={d.app.gauges} leds={d.app.leds} r={2} />
      <circle className="led" data-k="accent" data-on={sinceBuild < 3 ? "" : undefined} cx={d.app.build[0]} cy={d.app.build[1]} r={2.6} />
      {d.bucket.leds.map((p, k) => (
        <circle key={k} className="led" data-k="accent" data-on={k === 0 && b?.changed && sinceBuild >= 4 && sinceBuild < 12 ? "" : undefined} cx={p[0]} cy={p[1]} r={2} />
      ))}
      <circle className="led" data-k="ok" data-on={sinceCheck < 4 ? "" : undefined} cx={d.edge.led[0]} cy={d.edge.led[1]} r={2} />
      {d.monitor.pins.map((p, i) => (
        <circle key={i} className="pin" data-k={PIN_KINDS[i]} cx={p[0]} cy={p[1]} r={2.6} />
      ))}
      {fresh < 75 && (
        <g data-k="incident">
          <circle className="pin" cx={d.monitor.fresh[0]} cy={d.monitor.fresh[1]} r={3.2} />
          {fresh < 3 && <circle className="ping" cx={d.monitor.fresh[0]} cy={d.monitor.fresh[1]} r={3.2 + fresh * 3} />}
        </g>
      )}
      <circle className="led" data-k="ok" data-on="" cx={d.monitor.chipDot[0]} cy={d.monitor.chipDot[1]} r={1.8} />
      {packets && (
        <g>
          {st.fetching.map((p, i) => {
            if (p === null) return null;
            const q = along(d.paths.feeds[FEEDS.length - 1 - i], p);
            return <circle key={i} data-k={FEEDS[i].k} className="packet-k" cx={q[0]} cy={q[1]} r={3} />;
          })}
          {b?.changed && sinceBuild < 4 && (() => {
            const q = along(d.paths.upload, sinceBuild / 4);
            return <circle className="packet" cx={q[0]} cy={q[1]} r={3.2} />;
          })()}
          {check && <circle className={c?.ok200 ? "packet" : "packet-dim"} cx={check[0]} cy={check[1]} r={c?.ok200 ? 3.2 : 2.6} />}
          {apiPhase < 3 && (() => {
            const q = along(d.paths.api, apiPhase / 3);
            return <circle className="packet" cx={q[0]} cy={q[1]} r={3} />;
          })()}
        </g>
      )}
    </g>
  );
}

const STEPS = [
  ["rack", "Agency servers", "53 sources. Each is read on its own: once a copy is older than its refresh time, the next read fetches a new one."],
  ["app", "Our server: one copy per feed", "Each blade holds one feed's latest copy. The bar is the copy's age, the tick its refresh time (60 s to 5 min). A copy is kept 10 min to 6 h."],
  ["bucket", "Storage: three files", "live.json.gz is rebuilt every 30 s and uploaded only if it changed. signs.json.gz every 5 min, cameras.json.gz every hour."],
  ["edge", "Edge cache", "Serves the files to every map and holds each one for 15 s."],
  ["monitor", "The map", "Checks every 30 s and gets a 304 when nothing changed."],
  ["laptop", "REST API and MCP", "Answer from the same held copies, with data_as_of on every answer."],
] as const;

export default function D05Iso() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const s = useClock(play, SPEED, STILL, LOOP);
  const st = useMemo(() => stateAt(s), [s]);
  const d = ART.desk;
  return (
    <FigureFrame
      n={5}
      title="Where the data runs"
      hint={`Each blade holds one feed's copy: the bar is its age, the tick its refresh time · ${SPEED}× speed`}
      readout={sayAt(st)}
      legend={
        <div className="csf-keys dgf">
          {FEEDS.map((f) => (
            <span key={f.k} className="csf-key" data-k={f.k}>
              <span className="dg-key-dot" />
              {f.name}
            </span>
          ))}
        </div>
      }
      caption={
        <>
          Our server reads each agency feed on its own. A copy younger than its refresh time is served as it is;
          the first read after that serves it once more while a new copy is fetched behind it. Every {BUILD} seconds
          the server builds <code>live.json.gz</code> from the held copies and uploads it only if something changed.
          The map checks the edge cache every 30 s and gets a 304 when nothing did. The REST API and the MCP server
          answer from the same held copies, with <code>data_as_of</code> on every answer.
        </>
      }
    >
      <div ref={ref} className="dgf dg-iso" data-play={play ? "" : undefined}>
        <div className="csf-desk">
          <svg className="csf-svg" viewBox={`0 0 ${d.w} ${d.h + 40}`} role="img" aria-label="Isometric drawing on one base plate. Left, a rack of six agency servers, cabled to our server, which holds one blade per feed with a bar for the copy's age. A cable runs to storage holding three files (live, signs, cameras), then to an edge cache, then to a monitor showing the map. A laptop in front, wired to our server, stands for the REST API and MCP.">
            <Art html={d.art} />
            <Live st={st} d={d} packets={play} />
            <Label at={d.rack.top} dy={-40} title="Agency servers" sub="53 sources, each on its own timer" />
            <Label at={d.app.top} dy={-78} title="Our server: one held copy per feed" sub="refresh 60 s to 5 min · kept 10 min to 6 h" />
            <Label at={d.bucket.top} dy={-60} title="Storage: three files" sub="live 30 s · signs 5 min · cameras 1 h" />
            <Label at={d.edge.front} dy={74} title="Edge cache" sub="holds each file 15 s" />
            <Label at={d.monitor.front} dy={92} align="end" title="The map" sub="checks every 30 s · 304 if unchanged" />
            <Label at={d.laptop.front} dy={40} title="REST API and MCP" sub="read the held copies · data_as_of" />
          </svg>
        </div>
        <div className="csf-phone">
        <ol className="dg-iso-steps">
          {STEPS.map(([key, title, text]) => {
            const part = ART.phone[key];
            return (
              <li key={key} className="dg-iso-step" data-wide={key === "app" ? "" : undefined}>
                <svg className="dg-iso-mini" viewBox={`0 0 ${part.w} ${part.h}`} aria-hidden="true" style={{ maxWidth: part.w }}>
                  <Art html={part.art} />
                  {key === "rack" && <RackLeds st={st} leds={ART.phone.rack.anchors.leds} r={2} />}
                  {key === "app" && <Gauges st={st} gauges={ART.phone.app.anchors.gauges} leds={ART.phone.app.anchors.leds} r={1.8} />}
                  {key === "monitor" &&
                    ART.phone.monitor.anchors.pins.map((p, i) => <circle key={i} className="pin" data-k={PIN_KINDS[i]} cx={p[0]} cy={p[1]} r={2.4} />)}
                </svg>
                <div>
                  <h3 className="dg-step-h">{title}</h3>
                  <p className="dg-step-p">{text}</p>
                </div>
              </li>
            );
          })}
        </ol>
        </div>
      </div>
    </FigureFrame>
  );
}
