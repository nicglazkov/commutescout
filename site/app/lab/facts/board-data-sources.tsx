import { CodeBlock } from "@/components/docs/code-block";
import { Head, Opt, Stat } from "./kit";
import { ThumbMap } from "./thumb-map";
import {
  AGENCY_FEED_COUNT,
  CADENCES,
  CADENCE_MAX_S,
  COVERED_STATES,
  DEPTH_BUCKETS,
  FULL_STATES,
  LAYER_COUNTS,
  STATE_COUNT,
  STATE_COVERAGE_UPDATED,
} from "./facts-data";

const TITLE = "Where the data comes from";
const DEK = (
  <>
    CommuteScout reads {AGENCY_FEED_COUNT} official agency feeds from state transportation departments, highway patrols,
    and national weather and fire services, and puts them on one map.
  </>
);
const SRC_FEEDS = (
  <>
    {AGENCY_FEED_COUNT} = <code>AGENCY_FEED_COUNT</code>, {STATE_COUNT} = <code>STATE_COUNT</code> (site/lib/stats.ts, pinned by
    tests/test_snapshot.py).
  </>
);
const SRC_ROWS = (
  <>
    Per-layer and per-depth counts are computed live from the {COVERED_STATES} rows of <code>STATE_COVERAGE</code>{" "}
    (site/lib/state-coverage.ts, transcribed from docs/state-coverage.md). Any “Y…” cell counts.
  </>
);
const SRC_CADENCE = (
  <>
    Read intervals: the Refresh column of <code>CA_FEEDS</code> in site/lib/state-coverage.ts (the state with the most feeds), and
    for other states <code>TTL</code> (180 s), <code>CAM_TTL</code> and <code>WZDX_TTL</code> (600 s) in src/ca_roads_demo/states.py;
    map rebuild about every 30 s.
  </>
);

const DEPTH_LABEL: Record<number, string> = { 5: "All 5", 4: "4", 3: "3", 2: "2", 1: "1" };
const SAMPLE_ASOF = `"sources": [
  { "source": "incidents", "ok": true,
    "data_as_of": "2026-11-19T17:42:08+00:00" },
  { "source": "closures", "ok": true,
    "data_as_of": "2026-11-19T17:39:51+00:00" },
  { "source": "signs", "ok": false, "stale": true,
    "data_as_of": "2026-11-19T17:12:30+00:00" }
]`;

export function DataSourcesBoard() {
  const maxLayer = Math.max(...LAYER_COUNTS.map((l) => l.states));
  return (
    <>
      <Opt
        id="ds-1"
        n="DS1"
        name="Layer ledger"
        rec
        idea="Replace the three totals with what a visitor actually asks: which kinds of data, in how many states. One row per layer, a bar against all covered states."
        trade="Longer than a strip, and a little dense on a phone. It previews the coverage table below it, so the table can stay collapsed."
        src={<>{SRC_ROWS} Wildfires show “every state” per WILDFIRE_NOTE (national interagency fire service). {SRC_FEEDS}</>}
      >
        <Head title={TITLE} dek={DEK}>
          <div className="fx-ledger" role="table" aria-label={`States with each layer, out of ${COVERED_STATES}`}>
            <div role="rowgroup">
              {LAYER_COUNTS.map((l) => (
                <div role="row" key={l.key} className="fx-ledger-row">
                  <span role="rowheader" className="fx-ledger-name">
                    {l.label}
                    {l.note ? <em>{l.note}</em> : null}
                  </span>
                  <span role="cell" className="fx-ledger-bar" aria-hidden="true">
                    <i style={{ width: `${(l.states / maxLayer) * 100}%` }} data-layer={l.key} />
                  </span>
                  <span role="cell" className="fx-ledger-v">
                    {l.key === "wildfires" ? (
                      <>
                        <b>Every</b> state
                      </>
                    ) : (
                      <>
                        <b>{l.states}</b> states
                      </>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <p className="fx-foot">
            {AGENCY_FEED_COUNT} official feeds · {STATE_COUNT} states · traffic speeds, weather alerts and earthquakes cover every state
          </p>
        </Head>
      </Opt>

      <Opt
        id="ds-2"
        n="DS2"
        name="Map thumbnail with depth key"
        idea="A small, unlabelled coverage map beside the title, shaded by how many of the five live layers each state publishes, with the count per shade."
        trade="Most immediate answer to “is my state in?”, but it repeats the full coverage map lower on the page and needs care in dark mode."
        src={<>Shading = number of the five live layers (incidents, closures, cameras, signs, road weather) per row. {SRC_ROWS}</>}
      >
        <Head
          title={TITLE}
          dek={DEK}
          aside={
            <figure className="fx-mapcard">
              <ThumbMap />
              <figcaption>
                <ul className="fx-depthkey" aria-label="States by number of live layers">
                  {DEPTH_BUCKETS.map((b) => (
                    <li key={b.depth}>
                      <i data-depth={b.depth} aria-hidden="true" />
                      <span>{DEPTH_LABEL[b.depth]} layers</span>
                      <b>{b.states}</b>
                    </li>
                  ))}
                </ul>
              </figcaption>
            </figure>
          }
        />
      </Opt>

      <Opt
        id="ds-3"
        n="DS3"
        name="One depth bar"
        idea={`A single bar of all ${COVERED_STATES} covered states, split by how many live layers each has. It says “coverage is real but uneven” in one line, honestly.`}
        trade="Very compact and literal; reads as a chart, so it needs the short legend under it."
        src={SRC_ROWS}
      >
        <Head title={TITLE} dek={DEK}>
          <div className="fx-depthbar">
            <p className="fx-depthbar-h">
              <b>{COVERED_STATES} states</b> by how many of the five live layers their own agencies publish
            </p>
            <div className="fx-depthbar-track" role="img" aria-label={DEPTH_BUCKETS.map((b) => `${b.states} states with ${b.depth}`).join(", ")}>
              {DEPTH_BUCKETS.map((b) => (
                <span key={b.depth} data-depth={b.depth} style={{ flexGrow: b.states }}>
                  <b>{b.states}</b>
                </span>
              ))}
            </div>
            <ol className="fx-depthbar-key" aria-hidden="true">
              {DEPTH_BUCKETS.map((b) => (
                <li key={b.depth} style={{ flexGrow: b.states }}>
                  {DEPTH_LABEL[b.depth]}
                </li>
              ))}
            </ol>
          </div>
        </Head>
      </Opt>

      <Opt
        id="ds-4"
        n="DS4"
        name="Freshness ladder"
        idea="Lead with how fresh, not how many: one bar per kind of feed, its length the time between reads, on a shared 0 to 10 minute scale."
        trade="Speaks to trust better than counts. Exact intervals differ by state and feed, so the rows group the common cases."
        src={SRC_CADENCE}
      >
        <Head title={TITLE} dek={DEK}>
          <figure className="fx-ladder">
            <figcaption>How often each kind of feed is read, and how often the map is rebuilt from them</figcaption>
            <ol className="fx-ladder-rows">
              {CADENCES.map((c) => (
                <li key={c.label}>
                  <span className="fx-ladder-l">{c.label}</span>
                  <span className="fx-ladder-track" aria-hidden="true">
                    <i style={{ width: `${(c.s / CADENCE_MAX_S) * 100}%` }} />
                  </span>
                  <b>{c.every}</b>
                </li>
              ))}
            </ol>
            <div className="fx-ladder-ticks" aria-hidden="true">
              {[0, 2, 4, 6, 8, 10].map((m) => (
                <span key={m} style={{ left: `${(m / 10) * 100}%` }}>
                  {m === 0 ? "0" : `${m} min`}
                </span>
              ))}
            </div>
          </figure>
        </Head>
      </Opt>

      <Opt
        id="ds-5"
        n="DS5"
        name="Plain sentence, no strip"
        idea="Drop the boxes. Fold the facts into one sentence under the dek with the numbers set in tabular figures."
        trade="Calmest and most readable; loses the at-a-glance scan that a strip gives."
        src={<>{SRC_FEEDS} {FULL_STATES} = states where all five live layers are “Y…”. {SRC_ROWS}</>}
      >
        <Head title={TITLE} dek={DEK}>
          <p className="fx-sentence">
            <b>{AGENCY_FEED_COUNT}</b> feeds, <b>{STATE_COUNT}</b> states, <b>{FULL_STATES}</b> of them with every live layer. Each
            answer says when its data was last updated, and old data is marked, never hidden.
          </p>
        </Head>
      </Opt>

      <Opt
        id="ds-6"
        n="DS6"
        name="Who publishes it"
        idea="Show the kinds of agencies behind the feeds as a typed list, with the total as the one big number."
        trade="Answers “is this official?” directly. No per-type counts yet; adding them needs a source-type column in the docs."
        src={<>{SRC_FEEDS} Agency types: the page dek and OVERLAY_NOTE / WILDFIRE_NOTE in site/lib/state-coverage.ts.</>}
      >
        <Head title={TITLE} dek={DEK}>
          <div className="fx-who">
            <p className="fx-who-n">
              <b>{AGENCY_FEED_COUNT}</b>
              <span>official feeds</span>
            </p>
            <ul className="fx-who-list">
              <li>
                <b>State transportation departments</b>
                <span>Closures, work zones, cameras, message signs, road weather</span>
              </li>
              <li>
                <b>Highway patrols</b>
                <span>Crashes and hazards as dispatchers log them</span>
              </li>
              <li>
                <b>National Weather Service</b>
                <span>Warnings and forecasts, every state</span>
              </li>
              <li>
                <b>National fire service</b>
                <span>Active wildfires and mapped outlines, every state</span>
              </li>
            </ul>
          </div>
        </Head>
      </Opt>

      <Opt
        id="ds-7"
        n="DS7"
        name="What a response carries"
        idea="The trust story as the product shows it: a trimmed code card of per-source data_as_of timestamps, one of them marked stale."
        trade="Concrete for developers; abstract for someone who only uses the map. A sample, not a record."
        src={<>Keys from <code>source_status()</code> in src/ca_roads_mcp/serialize.py (source, ok, data_as_of, stale); real source ids are agency feed codes, shown here as generic names. Times are a sample.</>}
      >
        <Head
          title={TITLE}
          dek={DEK}
          aside={<CodeBlock code={SAMPLE_ASOF} lang="json" title="Part of every answer" className="fx-aside-code" />}
        >
          <ul className="fx-checks">
            <li>Road events from official agencies</li>
            <li>Every source timestamped</li>
            <li>Old data marked, never dropped</li>
          </ul>
        </Head>
      </Opt>

      <Opt
        id="ds-8"
        n="DS8"
        name="Two numbers, big"
        idea={`An editorial pair: ${STATE_COUNT} states and ${AGENCY_FEED_COUNT} feeds in display type, with one line each on what they mean.`}
        trade="Strong and simple; says nothing about depth, so the coverage section below has to carry it."
        src={SRC_FEEDS}
      >
        <Head title={TITLE} dek={DEK}>
          <ul className="fx-bignums">
            <li>
              <b>{STATE_COUNT}</b>
              <span>states with their own live feeds. Weather alerts, wildfires and traffic speeds cover the rest.</span>
            </li>
            <li>
              <b>{AGENCY_FEED_COUNT}</b>
              <span>official agency feeds, each read as its own layer and lined up on one map.</span>
            </li>
          </ul>
        </Head>
      </Opt>

      <Opt
        id="ds-9"
        n="DS9"
        name="Strip plus status line"
        idea="Keep today’s strip, but swap the third cell for freshness and add a dated line, so the header says when coverage was last checked."
        trade="Smallest change from what ships now. Still a box of numbers."
        src={<>{SRC_FEEDS} “Updated” = <code>STATE_COVERAGE_UPDATED</code> ({STATE_COVERAGE_UPDATED}). Freshness: {SRC_CADENCE}</>}
      >
        <Head title={TITLE} dek={DEK}>
          <ul className="dx-facts" data-count="4">
            <Stat v={AGENCY_FEED_COUNT} l="official feeds" />
            <Stat v={STATE_COUNT} l="states" />
            <Stat v="1 to 10 min" l="how often feeds are read" />
            <Stat v="~30 s" l="map rebuilt" />
          </ul>
          <p className="fx-status">
            <i aria-hidden="true" /> Coverage table checked {STATE_COVERAGE_UPDATED.split(" ")[0]}
          </p>
        </Head>
      </Opt>

      <Opt
        id="ds-10"
        n="DS10"
        name="Index card"
        idea="Treat the header as a table of contents: three cards that jump to the sections, each carrying its own headline figure."
        trade="Useful on a long page; the numbers become navigation rather than claims. Can look like three equal cards if not kept flat."
        src={<>{SRC_FEEDS} {SRC_ROWS} {SRC_CADENCE}</>}
      >
        <Head title={TITLE} dek={DEK}>
          <nav className="fx-index" aria-label="Jump to (mockup)">
            <a href="#ds-10">
              <span className="fx-index-k">Coverage by state</span>
              <b>{STATE_COUNT} states</b>
              <span>{FULL_STATES} with every live layer</span>
            </a>
            <a href="#ds-10">
              <span className="fx-index-k">How fresh it is</span>
              <b>1 to 10 min</b>
              <span>per feed, timestamped in every answer</span>
            </a>
            <a href="#ds-10">
              <span className="fx-index-k">The feeds</span>
              <b>{AGENCY_FEED_COUNT} feeds</b>
              <span>state, patrol, weather and fire agencies</span>
            </a>
          </nav>
        </Head>
      </Opt>
    </>
  );
}
