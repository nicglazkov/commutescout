import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import D01Swimlane from "./d01-swimlane";
import D02Timing from "./d02-timing";
import D03Journey from "./d03-journey";
import D04Matrix from "./d04-matrix";
import D05Iso from "./d05-iso";
import D06Console from "./d06-console";
import D07Dial from "./d07-dial";
import D08FanIn from "./d08-fanin";
import D09Normalise from "./d09-normalise";
import D10Coverage from "./d10-coverage";
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
    idea: "Each kind of source is a row: read on its own timer, held in memory, combined into one list, published as three files, read by the map. The API and MCP branch off the held copies.",
    trade: <><b>Best fit for “How it fits together”:</b> every stage and number is real. Dense at phone width; would need a stacked phone version.</>,
    fig: <D01Swimlane />,
  },
  {
    n: 2,
    name: "Timing diagram",
    idea: "Ten minutes to scale. Ticks show when each source is re-read, when each file is published and when the map checks for news.",
    trade: <><b>Answers “how fresh?” at a glance.</b> Says nothing about how sources are combined, so it fits “How fresh it is” better than here.</>,
    fig: <D02Timing />,
  },
  {
    n: 3,
    name: "One crash's journey",
    idea: "A single crash followed second by second from the dispatcher's log to a pin on the map, including the build that ships the old copy while it fetches a new one.",
    trade: <><b>The most concrete and memorable.</b> Covers one source, not all 53; pairs well with option 1 or 8.</>,
    fig: <D03Journey />,
  },
  {
    n: 4,
    name: "Who publishes what",
    idea: "Kinds of data against kinds of publisher, with how often each is re-read and how many states have it.",
    trade: <><b>Precise and accessible (a real table).</b> Least visual; overlaps with the coverage table further down the page.</>,
    fig: <D04Matrix />,
  },
  {
    n: 5,
    name: "Isometric system drawing",
    idea: "The physical parts in the site's isometric figure style: agency servers, the app holding a copy of each feed, storage with the three files, a browser with the map, an assistant calling the API.",
    trade: <><b>Keeps the house figure style</b> and shows where things run. Less exact about timing than 1 to 3.</>,
    fig: <D05Iso />,
  },
  {
    n: 6,
    name: "Feed health console",
    idea: "Every source with the age of its last good copy against its stale limit, and a fresh, stale or down status, as the apps' data-source screen shows it.",
    trade: <><b>Shows what happens when an agency fails</b>, which nothing else here does. Example rows, so it reads as a mockup unless wired to /api/sources.</>,
    fig: <D06Console />,
  },
  {
    n: 7,
    name: "Data-age dial",
    idea: "A 30-minute dial: the outer ring is one source's copy (fresh, then served marked stale, then dropped), the inner ring is the map's “Data as of” chip.",
    trade: <><b>Explains stale handling in one picture.</b> Two rings measure two different ages, which needs the key to read.</>,
    fig: <D07Dial />,
  },
  {
    n: 8,
    name: "Fan-in network",
    idea: "All 53 counted sources as dots, grouped by how they are published, converging on one list and fanning out to the three files, the REST API and MCP.",
    trade: <><b>Makes “53” tangible</b> and shows the shape of the system. No timing.</>,
    fig: <D08FanIn />,
  },
  {
    n: 9,
    name: "Two formats in, one out",
    idea: "A real XML lane closure and a real WZDx work zone, side by side, translated into the one marker format, with numbered field mappings.",
    trade: <><b>The most literal answer to “one map from many feeds”.</b> Code-heavy; best for the developer half of the audience.</>,
    fig: <D09Normalise />,
  },
  {
    n: 10,
    name: "Coverage map with source counts",
    idea: "Each state shaded and numbered by how many of the 53 sources cover it, counted from the code's source registries.",
    trade: <><b>Geographic and instantly readable.</b> Shows where, not how; closest to the existing coverage table.</>,
    fig: <D10Coverage />,
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
        Ten replacements for Fig. 1, “Many feeds, one map”, under “How it fits together” on <Link href="/data-sources" className="cs-link">/data-sources</Link>.
        Each one draws the real pipeline as the code runs it, with generic places only.
      </p>

      <section className="dg-rec" aria-labelledby="dg-rec-h">
        <h2 id="dg-rec-h">Recommendation: 1, Pipeline swimlane</h2>
        <p>
          It is the only option that shows every stage the section title promises, and every number in it comes from
          the code. If the page can carry a second figure, put 3 (one crash&apos;s journey) under “How fresh it is”.
          Runners-up: 8 for a lighter overview, 9 for a developer audience.
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
