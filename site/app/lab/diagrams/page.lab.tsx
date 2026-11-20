import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import D01Swimlane from "./d01-swimlane";
import D03Journey from "./d03-journey";
import D05Iso from "./d05-iso";
import "./diagrams.css";

// Local-only board (page.lab.tsx never builds in production). Ten replacements for
// Fig. 1 "Many feeds, one map" on /data-sources, under "How it fits together".

export const metadata: Metadata = {
  title: "Lab: data sources diagram (local only)",
  robots: { index: false, follow: false },
};

type Opt = { n: number; name: string; idea: string; trade: ReactNode; fig: ReactNode; pick?: boolean };

const OPTIONS: Opt[] = [
  {
    n: 1,
    name: "Pipeline swimlane",
    pick: true,
    idea: "Each kind of source is a row: re-read once its copy is older than its refresh time, held in memory, combined into one list, published as three files, read by the map. The API and MCP branch off the held copies.",
    trade: <><b>Shows every stage the section promises, with the real numbers.</b> The animation runs the 30-second build: stale rows refetch, a changed build uploads, the map gets a 200 or a 304. On a phone it becomes a stacked list of stages.</>,
    fig: <D01Swimlane />,
  },
  {
    n: 3,
    name: "One crash's journey",
    idea: "A single crash followed second by second from the dispatcher's log to a pin on the map, including the build that ships the old copy while it fetches a new one.",
    trade: <><b>The most concrete: 75 seconds you can follow.</b> One source only, so it explains freshness rather than the whole system. On a phone it becomes a vertical log.</>,
    fig: <D03Journey />,
  },
  {
    n: 5,
    name: "Isometric system drawing",
    idea: "The real machines on one base plate: agency servers, our server holding one copy per feed with an age gauge on each, storage with the three files, the edge cache, the map, and a laptop on the API.",
    trade: <><b>The house figure style, and it shows where each step runs.</b> Timing is in the gauges and lamps rather than written out; on a phone each machine gets its own row.</>,
    fig: <D05Iso />,
  },
];

const FACTS: [string, string][] = [
  ["Read", "Each source has its own refresh time: 60 s for incidents and traffic, 2.5 to 3 min for signs, cameras, road weather and other states, 5 min for closures, chains, fires, alerts, quakes, 10 min for work-zone feeds."],
  ["Hold", "A copy inside its refresh time is served as is; after it, served at once while a new copy is fetched behind it; a failed refresh keeps the copy, marked stale; past its keep time (10 min to 6 h) it is dropped."],
  ["Translate", "Every agency format (XML, JSON, WZDx GeoJSON, ArcGIS) becomes the same marker: kind, lat, lon, label, class, route, src."],
  ["Publish", "Every 30 s the app builds one list and writes live.json.gz; signs.json.gz every 5 min; cameras.json.gz every hour. Unchanged lists are not re-uploaded, and a build missing a feed is held back."],
  ["Deliver", "The map checks the edge every 30 s (a 304 when nothing changed). The REST API and MCP read the held copies on request, with data_as_of on every answer."],
  ["Watch", "Every 5 min a check looks for sources past their stale limit; two failures in a row raise an alert."],
];

export default function DiagramsBoard() {
  return (
    <main className="cs-container py-16 dg-board">
      <p className="text-sm text-cs-ink-3">
        <Link href="/lab" className="cs-link">Lab</Link> · local preview only, not part of the site
      </p>
      <h1 className="cs-display mt-2">Data sources diagram</h1>
      <p className="mt-4 max-w-2xl text-cs-ink-2">
        Three finalists to replace Fig. 1, “Many feeds, one map”, under “How it fits together” on <Link href="/data-sources" className="cs-link">/data-sources</Link>.
        Each one draws the real pipeline as the code runs it, with generic places only.
      </p>

      <section className="dg-rec" aria-labelledby="dg-rec-h">
        <h2 id="dg-rec-h">Recommendation: 1 for the section, 3 under “How fresh it is”</h2>
        <p>
          1 is still the only one that shows every stage the section title promises, with every number from the code,
          and it now runs the real 30-second cycle and stacks cleanly on a phone. 3 is the best second figure: it
          turns the same rules into 75 seconds a reader can follow. 5 is the most striking and matches the house
          figure style, but says the least in words; pick it if the page wants one picture rather than an explanation.
          1 and 5 run on one model of the pipeline (sim.ts) and 3 follows the same rules, so their numbers agree.
        </p>
      </section>

      <dl className="dg-facts" aria-label="How the pipeline works, from the code">
        {FACTS.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-12">
        {OPTIONS.map((o) => (
          <section key={o.n} className="dg-opt" id={`option-${o.n}`} aria-labelledby={`dg-${o.n}`}>
            <div className="dg-meta">
              <div className="dg-num">OPTION {String(o.n).padStart(2, "0")}</div>
              <h2 className="dg-name" id={`dg-${o.n}`}>
                {o.name}
                {o.pick && <span className="dg-pick-tag">Top pick</span>}
              </h2>
              <p className="dg-idea">{o.idea}</p>
              <p className="dg-trade">{o.trade}</p>
            </div>
            <div>{o.fig}</div>
          </section>
        ))}
      </div>
    </main>
  );
}
