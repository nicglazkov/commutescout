import { Card } from "@/components/ui/card";
import { ArrowLeftRight, Bell, LineChart, Users } from "lucide-react";

// Source: Tailark OSS registry, Dusk kit, dusk-features-1
// (https://oss.tailark.com/r/dusk-features-1.json).
//
// Adapted from upstream: text-muted-foreground/text-foreground/bg-background/
// bg-card/ring-foreground replaced with --cs-* tokens throughout. Upstream's
// copy was written for a CRM product ("deal stage", "pipeline"); replaced
// with neutral placeholder copy since a page composing this block owns its
// own real content.
export default function Features() {
  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <h2 className="text-cs-ink/60 max-w-4xl text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          <span className="text-cs-ink">Section headline placeholder.</span> <br /> One
          line of supporting copy.
        </h2>
        <div className="*:bg-cs-paper mt-8 grid gap-3 md:mt-16 md:grid-cols-2 lg:grid-cols-3">
          <Card className="p-8">
            <p className="text-cs-ink/60 max-w-xs text-lg font-medium">
              <span className="text-cs-ink">Feature headline.</span> One or two sentences
              describing this capability.
            </p>

            <div className="my-16">
              <div
                aria-hidden
                className="bg-cs-paper relative mx-auto aspect-square w-10/12 rounded-xl border border-cs-line"
              >
                <div className="bg-cs-paper ring-cs-ink/6.5 absolute bottom-0 right-0 aspect-square w-3/5 translate-x-8 translate-y-16 rounded-xl shadow-xl ring" />
              </div>
            </div>
          </Card>
          <Card className="lg:col-span-2">
            <div className="p-8">
              <p className="text-cs-ink/60 max-w-xs text-lg font-medium">
                <span className="text-cs-ink">Feature headline.</span> One or two
                sentences describing this capability.
              </p>
            </div>

            <div className="mask-x-from-65% mt-6 pt-2">
              <div
                aria-hidden
                className="bg-linear-to-b from-cs-ink/5 ring-cs-ink/6.5 relative h-72 rounded-xl shadow-xl ring"
              ></div>
            </div>
          </Card>
        </div>

        <div className="max-sm:*:not-last:border-cs-line max-sm:*:not-last:border-b max-sm:*:not-last:pb-3 mt-12 grid gap-3 *:max-w-xs sm:grid-cols-2 md:mt-16 md:gap-y-6 lg:mt-24 lg:grid-cols-4 lg:gap-6">
          <p className="text-cs-ink/60 text-balance">
            <span className="text-cs-ink font-medium">
              <ArrowLeftRight className="inline size-4 -translate-y-0.5" /> Capability one.
            </span>{" "}
            Placeholder description of this capability.
          </p>

          <p className="text-cs-ink/60 text-balance">
            <span className="text-cs-ink font-medium">
              <Bell className="inline size-4 -translate-y-0.5" /> Capability two.
            </span>{" "}
            Placeholder description of this capability.
          </p>

          <p className="text-cs-ink/60 text-balance">
            <span className="text-cs-ink font-medium">
              <Users className="inline size-4 -translate-y-0.5" /> Capability three.
            </span>{" "}
            Placeholder description of this capability.
          </p>

          <p className="text-cs-ink/60 text-balance">
            <span className="text-cs-ink font-medium">
              <LineChart className="inline size-4 -translate-y-0.5" /> Capability four.
            </span>{" "}
            Placeholder description of this capability.
          </p>
        </div>
      </div>
    </section>
  );
}
