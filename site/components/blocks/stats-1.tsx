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
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-4 md:grid-cols-2 md:gap-6">
          <h2 className="text-cs-ink max-w-4xl text-balance text-4xl font-medium tracking-tight lg:text-5xl">
            Coverage today
          </h2>
          <div className="flex flex-col gap-12 md:mx-auto">
            <p className="text-cs-ink/60 text-balance text-lg">
              Every answer names its sources and their timestamps. When a feed goes
              stale, CommuteScout says so instead of guessing.
            </p>

            <div className="grid gap-12 sm:grid-cols-3 md:gap-12">
              <div className="space-y-3 border-t border-cs-line pt-6">
                <div className="text-4xl font-semibold tracking-tight">{AGENCY_FEED_COUNT}</div>
                <p className="text-cs-ink/60">Agency feeds</p>
              </div>
              <div className="space-y-3 border-t border-cs-line pt-6">
                <div className="text-4xl font-semibold tracking-tight">{STATE_COUNT}</div>
                <p className="text-cs-ink/60">States</p>
              </div>
              <div className="space-y-3 border-t border-cs-line pt-6">
                <div className="text-2xl font-semibold tracking-tight">Per-source</div>
                <p className="text-cs-ink/60">Timestamps</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
