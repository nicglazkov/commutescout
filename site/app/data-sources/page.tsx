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

// Data sources page takes its own metadata, matching the shape every
// other marketing page uses (title/description/canonical/openGraph/
// twitter). Description is one sentence, Google style. Source for every
// factual claim on this page: docs/data-sources.md and
// docs/state-coverage.md; this page restyles those docs into a visual
// page rather than rewording their content (see AGENCY_FEED_COUNT/
// PUBLIC_SOURCE_COUNT drift guard note below the intro).
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

const INTRO_TEXT =
  "Everything CommuteScout serves comes from public agency feeds, " +
  "fetched live and cached briefly in-process.";

const FRESHNESS_TEXT =
  "No feed is ever silently dropped: every response carries per-source " +
  "data_as_of timestamps, and when a feed is stale or failing, the last " +
  "good data is served, flagged stale, with the error attached, so both " +
  "the UI and an AI assistant can say how much to trust the answer. " +
  "Caches are stale-while-revalidate: an expired feed is served from " +
  "memory instantly while one background task refreshes it, so " +
  "requests never wait on an upstream agency server.";

const TAXONOMY_INTRO =
  "Every closure record carries a closure_class derived from the " +
  "Caltrans facility and closure type. The raw feed marks an on-ramp " +
  "repair \"Full\", and reporting that as a closed highway would be " +
  "wrong, so the classes keep them apart.";

const LEGEND_TEXT =
  "Check = live on the map. Dash = the state's public feeds do not " +
  "offer it keylessly; the number links to the reason below. \"wz\" " +
  "next to a check means closures come from the state's WZDx roadwork " +
  "feed.";

export default function DataSourcesPage() {
  return (
    <>
      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-3xl px-6">
          <h1 className="text-cs-ink text-balance text-4xl font-medium tracking-tight lg:text-5xl">
            Data sources
          </h1>

          {/* The "53 official agency feeds" phrase and number are pinned
              by tests/test_snapshot.py::test_feed_counts_are_current,
              which scans this file alongside the README, the homepage
              hero, and site/lib/stats.ts. */}
          <p className="text-cs-ink/60 mt-6 text-balance md:text-lg">
            CommuteScout reads 53 official agency feeds. {INTRO_TEXT}
          </p>
        </div>
      </section>

      <section className="pb-16 md:pb-20" aria-labelledby="coverage-heading">
        <div className="mx-auto max-w-7xl px-6">
          <h2
            id="coverage-heading"
            className="text-cs-ink text-balance text-3xl font-medium tracking-tight md:text-4xl"
          >
            Coverage by state
          </h2>
          <p className="text-cs-ink/50 mt-2 text-sm">
            Updated {STATE_COVERAGE_UPDATED}. What each live state actually
            has on the map, and why the gaps exist.
          </p>

          <div className="mt-8">
            <StateCoverageTable rows={STATE_COVERAGE} />
          </div>

          <p className="text-cs-ink/50 mt-4 max-w-3xl text-xs text-balance">
            {LEGEND_TEXT}
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="bg-cs-bg rounded-lg p-4">
              <p className="text-cs-ink text-sm font-medium">Wildfires (*)</p>
              <p className="text-cs-ink/60 mt-1 text-sm">{WILDFIRE_NOTE}</p>
            </div>
            <div className="bg-cs-bg rounded-lg p-4">
              <p className="text-cs-ink text-sm font-medium">Cameras (**)</p>
              <p className="text-cs-ink/60 mt-1 text-sm">{CAMERA_SUBSET_NOTE}</p>
            </div>
          </div>

          <p className="text-cs-ink/50 mt-6 max-w-3xl text-sm text-balance">
            {OVERLAY_NOTE}
          </p>

          <details className="border-cs-line mt-8 rounded-xl border p-6">
            <summary className="text-cs-ink cursor-pointer text-sm font-medium">
              Why the gaps ({GAP_REASONS.length} reasons)
            </summary>
            <ol className="text-cs-ink/60 mt-4 space-y-3 text-sm">
              {GAP_REASONS.map((gap) => (
                <li key={gap.n} id={`gap-${gap.n}`} className="scroll-mt-6">
                  <span className="text-cs-ink font-medium">{gap.n}.</span>{" "}
                  {gap.text}
                </li>
              ))}
            </ol>
          </details>
        </div>
      </section>

      <section className="bg-cs-bg py-16 md:py-20" aria-labelledby="freshness-heading">
        <div className="mx-auto max-w-7xl px-6">
          <h2
            id="freshness-heading"
            className="text-cs-ink text-balance text-3xl font-medium tracking-tight md:text-4xl"
          >
            How freshness works
          </h2>
          <p className="text-cs-ink/60 mt-4 max-w-3xl text-balance md:text-lg">
            {FRESHNESS_TEXT}
          </p>

          <div className="ring-cs-line bg-cs-paper mt-10 overflow-x-auto rounded-xl ring-1">
            <table className="w-full min-w-[640px] border-collapse text-left text-sm">
              <thead>
                <tr>
                  <th className="border-b border-cs-line px-4 py-3 font-medium">Source</th>
                  <th className="border-b border-cs-line px-4 py-3 font-medium">Data</th>
                  <th className="border-b border-cs-line px-4 py-3 font-medium whitespace-nowrap">
                    Refresh
                  </th>
                </tr>
              </thead>
              <tbody>
                {CA_FEEDS.map((feed) => (
                  <tr key={feed.source} className="even:bg-cs-bg/40">
                    <td className="border-b border-cs-line px-4 py-3 font-medium whitespace-nowrap">
                      {feed.source}
                    </td>
                    <td className="text-cs-ink/70 border-b border-cs-line px-4 py-3">
                      {feed.data}
                    </td>
                    <td className="text-cs-ink/70 border-b border-cs-line px-4 py-3 whitespace-nowrap">
                      {feed.refresh}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="py-16 md:py-20" aria-labelledby="the-closure-taxonomy">
        <div className="mx-auto max-w-7xl px-6">
          <h2
            id="the-closure-taxonomy"
            className="text-cs-ink text-balance text-3xl font-medium tracking-tight md:text-4xl"
          >
            The closure taxonomy
          </h2>
          <p className="text-cs-ink/60 mt-4 max-w-3xl text-balance md:text-lg">
            {TAXONOMY_INTRO}
          </p>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CLOSURE_CLASSES.map((cls) => (
              <div
                key={cls.code}
                className="ring-cs-line bg-cs-paper flex flex-col gap-3 rounded-xl p-6 shadow ring-1"
              >
                <code className="bg-cs-bg text-cs-ink w-fit rounded-md px-2 py-1 text-xs font-medium">
                  {cls.code}
                </code>
                <p className="text-cs-ink text-sm">{cls.means}</p>
                <p className="text-cs-ink/50 mt-auto text-xs font-medium tracking-wide uppercase">
                  Can you drive through? <span className="text-cs-sky normal-case">{cls.drive}</span>
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="pb-16 md:pb-20">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="text-cs-ink text-balance text-3xl font-medium tracking-tight md:text-4xl">
            Hard-won parsing rules
          </h2>
          <p className="text-cs-ink/60 mt-4 text-balance">
            These feeds misbehave in production, and the parsers encode what
            we learned running them.
          </p>

          <ul className="text-cs-ink/60 mt-8 list-outside list-disc space-y-3 pl-5">
            {PARSING_RULES.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </div>
      </section>
    </>
  );
}
