import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";

// Source: Tailark OSS registry, Dusk kit, dusk-hero-section-1
// (https://oss.tailark.com/r/dusk-hero-section-1.json).
//
// Adapted from upstream:
// - Dropped the block's own embedded <HeroHeader /> nav: the site already
//   renders one global header (components/site-header.tsx) in app/layout.tsx,
//   so a second nav bar baked into the hero would compete with it.
// - Dropped the "trusted by" third-party logo strip (Spotify, Supabase,
//   Hulu, etc.) and the "New:" announcement pill: both were stock Tailark
//   content with no CommuteScout equivalent to fill them with.
// - Replaced the screenshot mockup with the two real screenshots captured
//   for Task 7 (site/public/shots/hero-map.png, hero-route.png), a wide
//   multi-state view and a Bay Area zoom, both from the live production map.
// - text-muted-foreground replaced with text-cs-ink/60; the rest of the
//   text inherits the page's --cs-ink color from the body rule in
//   app/globals.css, same as upstream relied on a global text-foreground.
// - Copy and hrefs are the homepage's real copy and links (Task 7's brief
//   copy is final and exact; this file owns it directly, not via props).
export default function HeroSection() {
  return (
    <section className="overflow-hidden">
      <div className="relative pt-24 md:pt-36">
        <div className="mx-auto max-w-7xl">
          <div className="px-6 text-center sm:mx-auto lg:mr-auto lg:mt-0">
            <h1 className="mx-auto mt-8 max-w-4xl text-balance text-5xl font-medium tracking-tight md:text-6xl lg:mt-12 xl:text-7xl">
              Live road conditions, straight from the source.
            </h1>
            <p className="text-cs-ink/60 mx-auto mt-4 max-w-2xl text-balance md:text-lg">
              CommuteScout reads 53 official agency feeds across 38 states: incidents,
              closures, chain controls, cameras, and wildfires on one live map.
            </p>

            <div className="mt-6 flex flex-col items-center justify-center gap-2 pb-8 md:flex-row">
              <Button
                nativeButton={false}
                render={
                  <Link href="/map">
                    <span className="text-nowrap">Open the map</span>
                  </Link>
                }
              />
              <Button
                variant="ghost"
                nativeButton={false}
                render={
                  <Link href="/pricing#waitlist">
                    <span className="text-nowrap">Get Pro updates</span>
                  </Link>
                }
              />
            </div>

            <div className="relative mx-auto mt-10 max-w-5xl pb-24 md:pb-32">
              <div className="overflow-hidden rounded-2xl shadow-2xl shadow-cs-navy/15 ring-1 ring-cs-line">
                <Image
                  src="/shots/hero-map.png"
                  alt="The CommuteScout live map showing incidents, closures, chain controls, and cameras across dozens of states"
                  width={1440}
                  height={900}
                  className="h-auto w-full"
                  priority
                />
              </div>
              <div className="absolute -bottom-10 -right-4 hidden w-64 overflow-hidden rounded-xl shadow-xl shadow-cs-navy/15 ring-1 ring-cs-line sm:block md:-right-10 md:w-80">
                <Image
                  src="/shots/hero-route.png"
                  alt="The map zoomed to the San Francisco Bay Area, showing local incidents and closures"
                  width={1440}
                  height={900}
                  className="h-auto w-full"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
