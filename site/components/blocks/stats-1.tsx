// Source: Tailark OSS registry, Dusk kit, dusk-stats-1
// (https://oss.tailark.com/r/dusk-stats-1.json). Satisfies the brief's
// "logo/stat band" required block type: a stats band rather than a
// third-party logo cloud, since CommuteScout has no partner logos to show.
//
// Adapted from upstream: text-muted-foreground/text-foreground replaced
// with --cs-* tokens; border-t replaced with border-t-cs-line. Upstream's
// CRM copy ("deals tracked") replaced with neutral placeholder copy and
// numbers.
export default function StatsSection() {
  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-4 md:grid-cols-2 md:gap-6">
          <h2 className="text-cs-ink/60 max-w-4xl text-balance text-4xl font-medium tracking-tight lg:text-5xl">
            <span className="text-cs-ink">Section headline placeholder.</span> <br /> One
            line of supporting copy.
          </h2>
          <div className="flex flex-col gap-32 md:mx-auto xl:gap-44">
            <p className="text-cs-ink/60 text-balance text-lg">
              Placeholder paragraph. A page composing this block replaces this copy and
              the stats below with real numbers.
            </p>

            <div className="grid gap-12 md:grid-cols-3 md:gap-12">
              <div className="space-y-3 border-t border-cs-line pt-6">
                <div className="text-4xl font-semibold tracking-tight">00</div>
                <p className="text-cs-ink/60">Stat label placeholder</p>
              </div>
              <div className="space-y-3 border-t border-cs-line pt-6">
                <div className="text-4xl font-semibold tracking-tight">00</div>
                <p className="text-cs-ink/60">Stat label placeholder</p>
              </div>
              <div className="space-y-3 border-t border-cs-line pt-6">
                <div className="text-4xl font-semibold tracking-tight">00</div>
                <p className="text-cs-ink/60">Stat label placeholder</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
