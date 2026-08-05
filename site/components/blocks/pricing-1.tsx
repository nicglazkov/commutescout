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
//
// Visual-engagement pass (polish phase 3): the flat two-column bordered
// grid is now framed in a --cs-navy "plinth" band so the pair reads as a
// deliberate comparison rather than two loose boxes; every checkmark sits
// in a small cs-sky/10 circle instead of a bare glyph; the Pro card gets a
// cs-sky ring, a lifted shadow, and its "Coming soon" marker moved from a
// corner ribbon to a pill badge for a clearer at-a-glance distinction.
// None of the bullet copy, plan names, CTA label, or badge text changed -
// only layout, color, and spacing.
export default function Pricing() {
  const freeItems = [
    "The full live map, all 38 states",
    "Route planner with GPX, KML, and print export",
    "Ask about your drive (daily cap)",
    "3 watch areas: circles up to 25 mi radius, polygons up to 2,000 sq mi, routes up to 250 mi with a 2 mi buffer",
  ];
  const proItems = [
    "More and larger watch areas",
    "Event history and playback",
    "Route briefings and exports",
  ];

  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <h1 className="text-cs-ink text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          Pricing
        </h1>

        <div className="bg-cs-navy mt-12 rounded-3xl p-2 lg:mt-16 lg:p-3">
          <div className="grid gap-3 max-lg:mx-auto max-lg:max-w-sm lg:grid-cols-2">
            <div className="bg-cs-paper flex flex-col gap-8 rounded-2xl p-6 transition-shadow hover:shadow-lg hover:shadow-cs-navy/10 sm:p-8">
              <div>
                <p className="text-cs-ink text-lg font-medium">Free</p>

                <Button
                  variant="outline"
                  className="mt-8 w-full"
                  nativeButton={false}
                  render={
                    <Link href="/map" prefetch={false}>
                      Open the map
                    </Link>
                  }
                />
              </div>

              <ul className="text-cs-ink/60 list-outside space-y-3">
                {freeItems.map((item, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="bg-cs-sky/10 text-cs-sky mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full">
                      <Check className="size-3" />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-cs-paper ring-cs-sky/50 relative flex flex-col gap-8 rounded-2xl p-6 shadow-xl shadow-cs-navy/20 ring-2 transition-shadow hover:shadow-2xl sm:p-8">
              <div className="bg-cs-sky absolute -top-3 left-6 w-fit rounded-full px-3 py-1 text-xs font-medium text-white shadow-sm shadow-cs-navy/20">
                Coming soon
              </div>

              <div>
                <p className="text-cs-ink text-lg font-medium">Pro</p>
              </div>

              <ul className="text-cs-ink/60 list-outside space-y-3">
                {proItems.map((item, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="bg-cs-sky/10 text-cs-sky mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full">
                      <Check className="size-3" />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
