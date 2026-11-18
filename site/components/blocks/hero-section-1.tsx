import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Smartphone } from "lucide-react";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";
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
// - Replaced the screenshot mockup with a real screenshot captured for
//   Task 7 (site/public/shots/hero-map.webp), a wide multi-state view from
//   the live production map. A second overlapping Bay Area card
//   (hero-route.png) was removed 2026-08-06 by project decision.
// - text-muted-foreground replaced with text-cs-ink/60; the rest of the
//   text inherits the page's --cs-ink color from the body rule in
//   app/globals.css, same as upstream relied on a global text-foreground.
// - 2026-11 redesign (Night Drive skin): the centered stack became a
//   left-aligned split. Headline on the left, the subhead and actions on
//   the right, the real map screenshot full width underneath with the
//   amber headlight glow pooled behind it. Same copy, same links.
// - Copy and hrefs are the homepage's real copy and links (Task 7's brief
//   copy is final and exact; this file owns it directly, not via props).
export default function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      <div className="mx-auto max-w-7xl px-6 pt-12 md:pt-20">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <p className="eyebrow flex items-center gap-2">
            {/* The live dot: the one bit of motion on the page, because the
                map behind it really is refreshing. Stops under reduced
                motion (globals.css). */}
            <span className="relative flex size-2" aria-hidden>
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-cs-sky opacity-60 [animation-duration:2.4s]" />
              <span className="relative inline-flex size-2 rounded-full bg-cs-sky" />
            </span>
            Live &middot; {AGENCY_FEED_COUNT} feeds &middot; {STATE_COUNT} states
          </p>
          {/* The app announcement. It is the first thing on the page
              after the header, so nobody has to scroll to learn the
              phone apps exist. */}
          <Link
            href="/app"
            prefetch={false}
            className="group inline-flex items-center gap-2 text-sm text-cs-muted transition-colors hover:text-cs-ink"
          >
            <span className="rounded-[4px] border border-cs-line px-1.5 py-0.5 font-mono text-[0.68rem] font-medium uppercase tracking-[0.12em] text-cs-ink">New</span>
            <span>CommuteScout Drive is on iPhone and Android</span>
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        </div>

        <div className="mt-8 grid gap-8 lg:grid-cols-12 lg:items-end lg:gap-10">
          <h1 className="display lg:col-span-8">
            Live road conditions, <span className="text-cs-sky">straight from the source.</span>
          </h1>
          <div className="lg:col-span-4 lg:pb-2">
            <p className="max-w-[46ch] text-lg leading-relaxed text-cs-muted">
              CommuteScout reads 53 official agency feeds across 37 states: incidents,
              closures, chain controls, cameras, and wildfires on one live map.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-2.5">
              <Button
                size="lg"
                nativeButton={false}
                render={
                  <Link href="/map" prefetch={false}>
                    <span className="text-nowrap">Open the map</span>
                  </Link>
                }
              />
              <Button
                size="lg"
                variant="secondary"
                nativeButton={false}
                render={
                  <Link href="/app" prefetch={false}>
                    <Smartphone aria-hidden />
                    <span className="text-nowrap">Get the app</span>
                  </Link>
                }
              />
              <Button
                size="lg"
                variant="ghost"
                nativeButton={false}
                render={
                  <Link href="/pricing#waitlist" prefetch={false}>
                    <span className="text-nowrap">Get Pro updates</span>
                  </Link>
                }
              />
            </div>
          </div>
        </div>
      </div>

      <div className="relative mx-auto mt-14 max-w-7xl px-4 pb-16 sm:px-6 md:mt-16 md:pb-24">
        {/* Headlight glow and road streaks behind the screenshot. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -bottom-10 h-3/4 bg-[radial-gradient(60%_70%_at_70%_100%,#ff9a3c40,transparent_70%)]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-[repeating-linear-gradient(100deg,transparent_0_46px,#ffb35c1c_46px_48px)] [mask-image:linear-gradient(transparent,#000)]"
        />
        {/* The whole screenshot links to the live map, so a click
            anywhere on it opens /map. focus-visible + hover give it
            a clickable affordance; the alt text is the label. */}
        <Link
          href="/map"
          prefetch={false}
          aria-label="Open the live map"
          className="relative block cursor-pointer overflow-hidden rounded-xl shadow-[0_40px_120px_-40px_#ff9a3c66,0_0_0_1px_var(--cs-line)] transition-shadow hover:shadow-[0_40px_120px_-30px_#ff9a3c99,0_0_0_1px_#ffb35c55] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cs-sky focus-visible:ring-offset-2 focus-visible:ring-offset-cs-bg"
        >
          <Image
            src="/shots/hero-map.webp"
            alt="The CommuteScout live map showing incidents, closures, chain controls, and cameras across dozens of states"
            width={1440}
            height={900}
            className="h-auto w-full"
            priority
          />
        </Link>
      </div>
    </section>
  );
}
