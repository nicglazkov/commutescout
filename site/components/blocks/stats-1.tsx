import Link from "next/link";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";

// Source: Tailark OSS registry, Dusk kit, dusk-stats-1
// (https://oss.tailark.com/r/dusk-stats-1.json). Satisfies the brief's
// "logo/stat band" required block type: a stats band rather than a
// third-party logo cloud, since CommuteScout has no partner logos to show.
// Used for the homepage's "data credibility band" (Task 7 brief).
//
// Adapted from upstream: text-muted-foreground/text-foreground replaced
// with --cs-* tokens; border-t replaced with border-t-cs-line. The two
// numeric stats come from lib/stats.ts, not hardcoded here, so they cannot
// drift from the hero subhead's own "53 ... 38 ..." copy; the drift guard
// is tests/test_snapshot.py::test_state_counts_are_current.
export default function StatsSection() {
  return (
    <section className="border-y border-cs-line bg-cs-navy/60 py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-10 md:grid-cols-12">
          <div className="md:col-span-5">
            <p className="eyebrow">Coverage today</p>
            <h2 className="mt-4">Every answer shows its source.</h2>
            <p className="mt-5 max-w-[46ch] text-lg leading-relaxed text-cs-muted">
              Every answer names its sources and their timestamps. When a feed goes
              stale, CommuteScout says so instead of guessing. See every feed on the{" "}
              <Link
                href="/data-sources"
                prefetch={false}
                className="text-cs-sky font-semibold underline-offset-4 hover:underline"
              >
                Data sources
              </Link>{" "}
              page.
            </p>
          </div>

          <dl className="grid gap-px self-end overflow-hidden rounded-[var(--site-radius)] border border-cs-line bg-cs-line sm:grid-cols-3 md:col-span-7">
            <div className="bg-cs-bg p-6">
              <dt className="eyebrow">Agency feeds</dt>
              <dd className="mt-6 font-display text-6xl font-extrabold tracking-[-0.04em] text-cs-sky">{AGENCY_FEED_COUNT}</dd>
            </div>
            <div className="bg-cs-bg p-6">
              <dt className="eyebrow">States</dt>
              <dd className="mt-6 font-display text-6xl font-extrabold tracking-[-0.04em]">{STATE_COUNT}</dd>
            </div>
            <div className="bg-cs-bg p-6">
              <dt className="eyebrow">Timestamps</dt>
              <dd className="mt-6 font-display text-3xl font-extrabold leading-[3.75rem] tracking-[-0.03em]">Per-source</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}
