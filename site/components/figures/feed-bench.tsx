"use client";

import { useEffect, useRef, useState } from "react";
import { AGENCY_FEED_COUNT } from "@/lib/stats";
import { FigureFrame } from "./frame";
import { BENCH_GEOM, BENCH_MARKS, BENCH_SVG, BENCH_VIEW } from "./feed-bench.art";
import { mountBench, type BenchController } from "./feed-bench.runtime";

// The sorting bench: how many official feeds become one live feed.
// Drawing: _build/bench (anatomy kit, isometric, four-tone shading, painter's order).
// What it shows, against the code:
// - every record keeps its source's own time: FeedResult.data_as_of (src/ca_roads/models.py:192-207),
//   stamped at fetch (TTLCache _Entry.fetched_at, src/ca_roads/cache.py)
// - duplicates: two records from DIFFERENT sources, same family, within DEDUPE_METERS = 120 m are one
//   event and the higher-trust source stays (src/ca_roads/dedupe.py:29, _PRIORITY). Same source is never
//   merged. Applied to route and corridor answers (src/ca_roads_mcp/server.py:595, :1264).
// - freshness: a source past its limit is still served and flagged stale, never dropped
//   (src/ca_roads/cache.py stale-while-revalidate; limits in src/ca_roads_demo/freshness.py:36-44)
// - one build feeds every outlet: build_markers is shared by the endpoint and the snapshot publisher
//   (src/ca_roads_demo/app.py:1113), live.json.gz rebuilt every 30 s (src/ca_roads_demo/snapshot.py:63-72),
//   read by the map, the apps, and the MCP/REST trip tools.
const FEEDS = ["Incident logs", "Closures and roadwork", "Chain controls", "Signs and road weather", "Weather alerts and wildfires"];
const INITIAL = [false, false, true, false, false];
const STATIONS: [string, string, string][] = [
  ["feeds", "Feeds in.", `Each chute is one kind of feed; ${AGENCY_FEED_COUNT} official feeds pour into five.`],
  ["stamp", "Stamp.", "Every record keeps the time its own source gave it."],
  ["dedupe", "Duplicates out.", "Two feeds, same event, within 120 m: the more trusted record stays."],
  ["gauge", "Freshness gauge.", "A feed past its stale limit still goes out, flagged, never hidden."],
  ["split", "Splitter.", "The same record goes to every outlet."],
  ["app", "Map, app, MCP and REST.", "One picture, read four ways."],
];

export default function FeedBench({ n = 1 }: { n?: number | string }) {
  const stage = useRef<HTMLDivElement>(null);
  const ctl = useRef<BenchController | null>(null);
  const [stale, setStale] = useState(INITIAL);
  const [readout, setReadout] = useState(`${AGENCY_FEED_COUNT} feeds · 1 stale, still served · 1 duplicate dropped`);

  useEffect(() => {
    if (!stage.current) return;
    const c = mountBench(stage.current, BENCH_GEOM, { feedCount: AGENCY_FEED_COUNT, initialStale: INITIAL, onReadout: setReadout });
    ctl.current = c;
    return () => {
      c.destroy();
      ctl.current = null;
    };
  }, []);

  const toggle = (i: number) => {
    const next = stale.slice();
    next[i] = !next[i];
    setStale(next);
    ctl.current?.setStale(i, next[i]);
  };

  return (
    <FigureFrame
      n={n}
      title={`How ${AGENCY_FEED_COUNT} feeds become one live feed`}
      className="csf-bench"
      hint="Press a feed: its next records leave flagged stale"
      readout={readout}
      controls={
        <div className="csf-controls" role="group" aria-label="Make a feed go stale">
          <span className="csf-controls-label">Make a feed go stale:</span>
          {FEEDS.map((f, i) => (
            <button key={f} type="button" className="csf-chip" data-tone="stale" aria-pressed={stale[i]} onClick={() => toggle(i)}>
              <span className="csf-chip-dot" aria-hidden="true" />
              {f}
            </button>
          ))}
        </div>
      }
      legend={
        <ol className="csf-stations">
          {STATIONS.map(([key, b, t], i) => (
            <li key={key}>
              <span className="csf-mk" aria-hidden="true">
                {i + 1}
              </span>
              <span>
                <b>{b}</b> {t}
              </span>
            </li>
          ))}
        </ol>
      }
    >
      <div className="csf-bench-wrap">
        <div className="csf-bench-stage" ref={stage}>
          <svg
            className="csf-svg iso bench-svg"
            viewBox={`0 0 ${BENCH_VIEW.W} ${BENCH_VIEW.H}`}
            role="img"
            aria-label={`A sorting bench: five feed chutes drop records onto a belt; a press stamps each with its source's own time; a pusher removes a duplicate another feed already reported within 120 meters; a gauge flags records from a feed past its stale limit, which still go out; a splitter sends the same record to the live map, the phone app, and the MCP and REST terminal.`}
            dangerouslySetInnerHTML={{ __html: BENCH_SVG }}
          />
          <div className="csf-marks" aria-hidden="true">
            {STATIONS.map(([key], i) => (
              <span key={key} className="csf-mk" style={{ left: `${BENCH_MARKS[key][0]}%`, top: `${BENCH_MARKS[key][1]}%` }}>
                {i + 1}
              </span>
            ))}
          </div>
        </div>
      </div>
    </FigureFrame>
  );
}
