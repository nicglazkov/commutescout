import type { Metadata } from "next";
import {
  CA_FEEDS,
  CAMERA_SUBSET_NOTE,
  CLOSURE_CLASSES,
  GAP_REASONS,
  OVERLAY_NOTE,
  PARSING_RULES,
  STATE_COVERAGE,
  STATE_COVERAGE_UPDATED,
  WILDFIRE_NOTE,
} from "@/lib/state-coverage";
import { StateCoverageTable } from "@/components/state-coverage-table";
import { DocsShell, Section, type TocItem } from "@/components/docs/docs-shell";
import { C } from "@/components/docs/code-block";
import { DocFigure } from "@/components/docs/doc-figure";

// Data sources page. Source for every factual claim: docs/data-sources.md
// and docs/state-coverage.md (through lib/state-coverage.ts), with cache
// times checked against src/ca_roads/feeds/* and the stale limits against
// src/ca_roads_demo/freshness.py. The "53 official agency feeds" phrase is
// pinned by tests/test_snapshot.py::test_feed_counts_are_current.
export const metadata: Metadata = {
  title: "Data sources - CommuteScout",
  description:
    "Every official feed behind CommuteScout, how fresh each one is, and what is live in every state it covers, with the reason for every gap.",
  alternates: {
    canonical: "https://commutescout.com/data-sources",
  },
  openGraph: {
    title: "Data sources - CommuteScout",
    description:
      "Every official feed behind CommuteScout, how fresh each one is, and what is live in every state it covers, with the reason for every gap.",
    url: "https://commutescout.com/data-sources",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

const TOC: TocItem[] = [
  { id: "coverage", label: "Coverage by state" },
  { id: "gaps", label: "Why the gaps" },
  { id: "freshness", label: "How freshness works" },
  { id: "feeds", label: "California feeds" },
  { id: "closures", label: "The closure taxonomy" },
  { id: "parsing", label: "Parsing rules" },
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
      eyebrow="Data sources"
      title="Official feeds, with their timestamps attached."
      dek={
        <>
          CommuteScout reads 53 official agency feeds. Everything it serves comes from public agency
          feeds, fetched live and cached briefly in-process, and every answer says how old each source is.
        </>
      }
      facts={[
        { value: "53", label: "official agency feeds" },
        { value: String(STATE_COVERAGE.length), label: "states live on the map" },
        { value: "Every", label: "response carries data_as_of" },
        { value: String(GAP_REASONS.length), label: "gaps, each with its reason" },
      ]}
      toc={TOC}
    >
      <Section id="coverage" kicker="Coverage" title="What each state has">
        <div className="dx-prose dx-lead">
          <p>
            Updated {STATE_COVERAGE_UPDATED}. A check means the layer is live on the map. A dash means the
            state&apos;s public feeds do not offer it without a key; its number links to the reason.
            &ldquo;(wz)&rdquo; next to a check means closures come from the state&apos;s WZDx roadwork feed.
          </p>
        </div>
        <StateCoverageTable rows={STATE_COVERAGE} />
        <div className="dx-cards">
          <div className="dx-card dx-card--plain">
            <h3>Wildfires (*)</h3>
            <p>{WILDFIRE_NOTE}</p>
          </div>
          <div className="dx-card dx-card--plain">
            <h3>Cameras (**)</h3>
            <p>{CAMERA_SUBSET_NOTE}</p>
          </div>
        </div>
        <p className="dx-small dx-mt-16 dx-measure">
          {OVERLAY_NOTE}
        </p>
      </Section>

      <Section id="gaps" kicker="Gaps" title="Why the gaps">
        <div className="dx-prose dx-lead">
          <p>
            Every dash in the table has one of these {GAP_REASONS.length} reasons. Most are a state that does
            not publish the data, or publishes it only behind a separate agreement.
          </p>
        </div>
        <details className="dx-details">
          <summary>Show all {GAP_REASONS.length} reasons</summary>
          <div className="dx-details-body">
            <ol className="dx-rules dx-rules--compact">
              {GAP_REASONS.map((gap) => (
                <li key={gap.n} id={`gap-${gap.n}`}>
                  <span>{gap.text}</span>
                </li>
              ))}
            </ol>
          </div>
        </details>
      </Section>

      <Section id="freshness" kicker="Freshness" title="How freshness works">
        <div className="dx-prose dx-lead">
          <p>
            No feed is ever silently dropped. Every response carries a <C>data_as_of</C> time for each
            source, and when a feed is stale or failing, the last good data is served, flagged stale, with
            the error attached, so both the map and an AI assistant can say how much to trust the answer.
          </p>
          <p>
            Caches are stale-while-revalidate: an expired feed is served from memory at once while one
            background task refreshes it, so a request never waits on an agency server. A watchdog checks
            every source every 5 minutes, and a source past its own stale limit on two checks in a row is
            reported to the operator.
          </p>
        </div>
        <DocFigure name="feed-cadence" />
      </Section>

      <Section id="feeds" kicker="California" title="The California feeds">
        <div className="dx-prose dx-lead">
          <p>
            California publishes the deepest feeds, so it has the most layers. &ldquo;Stale after&rdquo; is
            the age at which the watchdog reports a source; every other state&apos;s feeds share a 90-minute
            limit.
          </p>
        </div>
        <div className="dx-tbox">
          <table className="dx-table dx-table--stack">
            <caption className="sr-only">California feeds and how often each refreshes</caption>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Data</th>
                <th scope="col">Refresh</th>
                <th scope="col">Stale after</th>
              </tr>
            </thead>
            <tbody>
              {CA_FEEDS.map((feed) => (
                <tr key={feed.source}>
                  <th scope="row">{feed.source}</th>
                  <td data-label="Data">{feed.data}</td>
                  <td data-label="Refresh">{feed.refresh}</td>
                  <td data-label="Stale after">{feed.stale ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="closures" kicker="Closures" title="The closure taxonomy">
        <div className="dx-prose dx-lead">
          <p>
            Every closure record carries a <C>closure_class</C> derived from the Caltrans facility and
            closure type. The raw feed marks an on-ramp repair &ldquo;Full&rdquo;, and reporting that as a
            closed highway would be wrong, so the classes keep them apart.
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

      <Section id="parsing" kicker="In production" title="Hard-won parsing rules">
        <div className="dx-prose dx-lead">
          <p>These feeds misbehave in production, and the parsers encode what running them taught.</p>
        </div>
        <ol className="dx-rules">
          {PARSING_RULES.map((rule) => (
            <li key={rule}>
              <span>{rule}</span>
            </li>
          ))}
        </ol>
      </Section>
    </DocsShell>
  );
}
