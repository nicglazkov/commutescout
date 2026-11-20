import type { Metadata } from "next";
import {
  CA_FEEDS,
  CAMERA_SUBSET_NOTE,
  CLOSURE_CLASSES,
  OVERLAY_NOTE,
  STATE_COVERAGE,
  STATE_COVERAGE_UPDATED,
  WILDFIRE_NOTE,
  type StateRow,
} from "@/lib/state-coverage";
import { AGENCY_FEED_COUNT, TOLL_FEED_COUNT } from "@/lib/stats";
import { StateCoverageTable } from "@/components/state-coverage-table";
import { DocsShell, Section, type TocItem } from "@/components/docs/docs-shell";
import { C } from "@/components/docs/code-block";
import { DocFigure } from "@/components/docs/doc-figure";

// Data sources page. Source for every factual claim: docs/data-sources.md
// and docs/state-coverage.md (through lib/state-coverage.ts), with cache
// times checked against src/ca_roads/feeds/*. The "54 official agency
// feeds" phrase in the dek is pinned by
// tests/test_snapshot.py::test_feed_counts_are_current.
//
// Kept off this page on purpose (owner review, 2026-11-19): per-gap
// reasons that name keys and access arrangements, parsing internals, and
// how sources are monitored.
export const metadata: Metadata = {
  title: "Data sources - CommuteScout",
  description: "The official feeds behind CommuteScout, what each state publishes, and how fresh the data is.",
  alternates: {
    canonical: "https://commutescout.com/data-sources",
  },
  openGraph: {
    title: "Data sources - CommuteScout",
    description: "The official feeds behind CommuteScout, what each state publishes, and how fresh the data is.",
    url: "https://commutescout.com/data-sources",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

// The five live layers a state's own feeds can publish. Chains are
// seasonal and wildfires are national, so neither counts (the same rule
// as the coverage map figure).
const DEPTH_KEYS: (keyof StateRow)[] = ["incidents", "closures", "cameras", "signs", "weather"];
const FULL_STATES = STATE_COVERAGE.filter((r) => DEPTH_KEYS.every((k) => r[k].startsWith("Y"))).length;

// The head's ledger: each layer a state's own feeds can publish, and in
// how many of the covered states it is live (a "Y" cell in the coverage
// table). Wildfires are national (WILDFIRE_NOTE), so they sit under the
// ledger with the other every-state layers (OVERLAY_NOTE) instead of as a row.
const LEDGER: { key: keyof StateRow; label: string; note?: string }[] = [
  { key: "incidents", label: "Crashes and incidents" },
  { key: "closures", label: "Closures and work zones" },
  { key: "cameras", label: "Cameras" },
  { key: "signs", label: "Message signs" },
  { key: "weather", label: "Road weather" },
  { key: "chains", label: "Chain controls", note: "seasonal" },
];
const LEDGER_ROWS = LEDGER.map((l) => ({
  ...l,
  states: STATE_COVERAGE.filter((r) => r[l.key].startsWith("Y")).length,
}));

function LayerLedger() {
  const total = STATE_COVERAGE.length;
  return (
    <figure className="dx-ledger">
      <figcaption className="dx-ledger-cap">
        <span className="dx-head-k" id="ledger-k">
          Live layers by state
        </span>
        <span>of {total} states</span>
      </figcaption>
      <table aria-labelledby="ledger-k">
        <tbody>
          {LEDGER_ROWS.map((l) => (
            <tr key={l.key}>
              <th scope="row">
                {l.label}
                {l.note ? <em>{l.note}</em> : null}
              </th>
              <td className="dx-ledger-bar" aria-hidden="true">
                <i style={{ width: `${(l.states / total) * 100}%` }} data-seasonal={l.note ? "" : undefined} />
              </td>
              <td className="dx-ledger-v">
                <b>{l.states}</b> states
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="dx-ledger-foot">
        <b>Every state:</b> wildfires, live traffic speeds, National Weather Service alerts and earthquakes.{" "}
        <a href="#coverage" className="dx-link">
          Coverage by state
        </a>
      </p>
    </figure>
  );
}

const TOC: TocItem[] = [
  { id: "how", label: "How it fits together" },
  { id: "coverage", label: "Coverage by state" },
  { id: "freshness", label: "How fresh it is" },
  { id: "feeds", label: "California feeds" },
  { id: "closures", label: "Closure types" },
];

function driveTone(drive: string) {
  if (drive === "No") return "no";
  if (/delay/i.test(drive)) return "delay";
  return "yes";
}

export default function DataSourcesPage() {
  return (
    <DocsShell
      current="/data-sources"
      title="Where the data comes from"
      dek={
        <>
          CommuteScout reads 54 official agency feeds from state transportation departments, highway
          patrols, and national weather and fire services, and puts them on one map. Toll prices come
          from {TOLL_FEED_COUNT} separate toll-price feeds.
        </>
      }
      headExtra={
        <p className="dx-head-stats">
          <span>
            <b>{AGENCY_FEED_COUNT}</b> official feeds
          </span>
          <span>
            <b>{TOLL_FEED_COUNT}</b> toll-price feeds
          </span>
          <span>
            <b>{STATE_COVERAGE.length}</b> states
          </span>
          <span>
            <b>{FULL_STATES}</b> with all five year-round layers
          </span>
        </p>
      }
      aside={<LayerLedger />}
      toc={TOC}
    >
      <Section id="how" title="How it fits together">
        <div className="dx-prose dx-lead">
          <p>
            Each agency publishes one kind of information, such as crashes, closures or chain controls.
            CommuteScout checks each one on its own schedule, keeps a copy, and combines them into one map.
          </p>
        </div>
        <DocFigure name="pipeline-flow" />
      </Section>

      <Section id="coverage" title="Coverage by state">
        <div className="dx-prose dx-lead">
          <p>
            A check means the state publishes that information and it is live on the map. A dash means the
            state does not publish it publicly. Updated {STATE_COVERAGE_UPDATED.split(" ")[0]}.
          </p>
        </div>
        <StateCoverageTable rows={STATE_COVERAGE} />
        <ul className="dx-list dx-mt-20 dx-measure">
          <li>
            <b>roadwork</b>: closures come from the state&apos;s roadwork feed. <b>passes</b>: chain rules
            for mountain passes. <b>some</b>: part of the state.
          </li>
          <li>{WILDFIRE_NOTE}</li>
          <li>{CAMERA_SUBSET_NOTE}</li>
          <li>{OVERLAY_NOTE}</li>
        </ul>
      </Section>

      <Section id="freshness" title="How fresh it is">
        <div className="dx-prose dx-lead">
          <p>
            Every answer shows when each source last updated, as <C>data_as_of</C>. If a source falls behind,
            its last data stays on the map and is marked as old.
          </p>
        </div>
      </Section>

      <Section id="feeds" title="California feeds">
        <div className="dx-prose dx-lead">
          <p>California publishes the most, so it has the most layers. Refresh is how often CommuteScout reads each one.</p>
        </div>
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">California feeds and how often each is read</caption>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Data</th>
                <th scope="col">Refresh</th>
              </tr>
            </thead>
            <tbody>
              {CA_FEEDS.map((feed) => (
                <tr key={feed.source}>
                  <th scope="row">{feed.source}</th>
                  <td data-label="Data">{feed.data}</td>
                  <td data-label="Refresh">{feed.refresh}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="closures" title="Closure types">
        <div className="dx-prose dx-lead">
          <p>
            Not every closure stops traffic. A closed on-ramp is not a closed highway, so each closure carries
            a <C>closure_class</C> that says what it means for drivers.
          </p>
        </div>
        <ul className="dx-classes" aria-label="Closure classes">
          {CLOSURE_CLASSES.map((cls) => (
            <li key={cls.code}>
              <code>{cls.code}</code>
              <p>{cls.means}</p>
              <span className="dx-drive" data-v={driveTone(cls.drive)}>
                <span className="sr-only">Can you drive through? </span>
                {cls.drive}
              </span>
            </li>
          ))}
        </ul>
      </Section>
    </DocsShell>
  );
}
