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
import { AGENCY_FEED_COUNT } from "@/lib/stats";
import { StateCoverageTable } from "@/components/state-coverage-table";
import { DocsShell, Section, type TocItem } from "@/components/docs/docs-shell";
import { C } from "@/components/docs/code-block";
import { DocFigure } from "@/components/docs/doc-figure";

// Data sources page. Source for every factual claim: docs/data-sources.md
// and docs/state-coverage.md (through lib/state-coverage.ts), with cache
// times checked against src/ca_roads/feeds/*. The "53 official agency
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
          CommuteScout reads 53 official agency feeds from state transportation departments, highway
          patrols, and national weather and fire services, and puts them on one map.
        </>
      }
      facts={[
        { value: String(AGENCY_FEED_COUNT), label: "official feeds" },
        { value: String(STATE_COVERAGE.length), label: "states" },
        { value: String(FULL_STATES), label: "states with every live layer" },
      ]}
      toc={TOC}
    >
      <Section id="how" title="How it fits together">
        <div className="dx-prose dx-lead">
          <p>
            Each agency publishes one kind of information, such as crashes, closures or chain controls.
            CommuteScout reads each one as its own layer and lines them all up on the same map.
          </p>
        </div>
        <DocFigure name="map-layers" />
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
