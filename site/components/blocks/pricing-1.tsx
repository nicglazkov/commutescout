import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";

// Source: Tailark OSS registry, Dusk kit, dusk-pricing-1
// (https://oss.tailark.com/r/dusk-pricing-1.json). Reduced from the
// upstream four-tier grid (Starter/Pro/Startup/Enterprise, $19-$299) to
// CommuteScout's real two-tier plan (Free/Pro); the pricing page task
// (this file) owns the real plan copy.
//
// Complete/Quartz evaluated first (tailark.com/r/pricing-1..5.json,
// gated, fetched with Nic's key via x-api-key auth - confirmed working;
// Bearer auth 401s). None used: all five variants ship a client-side
// monthly/annually billing toggle plus an animated NumberFlow price
// counter (@number-flow/react dependency) - neither applies here, since
// neither card shows a price (Free lists usage limits, not a number;
// Pro's brief explicitly forbids one). pricing-2/-3/-4 are three/
// four-tier grids, a shape mismatch for a two-card page; pricing-5 is a
// single-plan layout. pricing-1 is the only two-tier variant, but
// stripping its billing toggle, its NumberFlow price display, its "use
// client" directive, and the @number-flow/react dependency it needs
// leaves the same shape as this already-vendored Dusk block - no
// material gain from switching. The "Coming soon" corner-ribbon styling
// on the Pro card borrows the free registry's own dusk-pricing-2
// "Popular" badge treatment (https://oss.tailark.com/r/dusk-pricing-2.json),
// recolored to --cs-sky instead of upstream's emerald.
//
// Adapted from upstream: text-muted-foreground/text-foreground/bg-card
// replaced with --cs-* tokens; bare "border" utilities (transparent by
// default in Tailwind v4) given an explicit border-cs-line color; the
// check icon uses cs-sky as a small accent instead of a neutral gray.
export default function Pricing() {
  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <h1 className="text-cs-ink text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          Pricing
        </h1>

        <div className="mt-12 grid gap-1.5 border border-cs-line *:p-6 max-lg:mx-auto max-lg:max-w-sm lg:mt-16 lg:grid-cols-2">
          <div className="flex flex-col gap-8 border-cs-line max-lg:border-b lg:border-r">
            <div>
              <p className="text-lg font-medium">Free</p>

              <Button
                variant="outline"
                className="mt-8 w-full"
                nativeButton={false}
                render={<Link href="/map">Open the map</Link>}
              />
            </div>

            <ul className="text-cs-ink/60 list-outside space-y-3">
              {[
                "The full live map, all 38 states",
                "Route planner with GPX, KML, and print export",
                "Ask about your drive (daily cap)",
                "3 watch areas: circles up to 25 mi radius, polygons up to 2,000 sq mi, routes up to 250 mi with a 2 mi buffer",
              ].map((item, index) => (
                <li key={index} className="flex items-start gap-3">
                  <Check className="text-cs-sky mt-1 size-3 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-cs-paper border-cs-line relative flex flex-col gap-8 max-lg:border-t lg:border-l">
            <div className="bg-cs-sky/15 text-cs-sky ring-cs-sky/20 absolute right-0 top-0 w-fit -translate-y-px translate-x-px rounded-bl-lg px-3 py-1 text-xs font-medium ring-1">
              Coming soon
            </div>

            <div>
              <p className="text-lg font-medium">Pro</p>
            </div>

            <ul className="text-cs-ink/60 list-outside space-y-3">
              {[
                "More and larger watch areas",
                "Event history and playback",
                "Route briefings and exports",
              ].map((item, index) => (
                <li key={index} className="flex items-start gap-3">
                  <Check className="text-cs-sky mt-1 size-3 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
