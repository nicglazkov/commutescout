import Image from "next/image";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrandMark } from "@/components/brand/brand-mark";

// The homepage hero. A left-aligned split: the claim, one line on what the
// map shows, two actions, and a real screenshot of the live map on the
// right (light and dark captures of /map, swapped by the site theme).
// The copy never names the area the screenshot shows.
//
// The counts in the lede are pinned by tests/test_snapshot.py
// (test_state_counts_are_current, test_feed_counts_are_current), which
// read this file for "N official sources" and "across N states".
export default function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      <div className="cs-container grid items-center gap-12 pb-16 pt-12 md:pb-24 md:pt-20 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          {/* The launch announcement: a real pill with the app's icon, a
              solid "New" tag and the product name, so it reads as news
              and as a link at a glance. */}
          <Link
            href="/app"
            prefetch={false}
            className="group cs-rise inline-flex max-w-full items-center gap-2.5 rounded-full border border-cs-line-strong bg-cs-surface py-1.5 pl-1.5 pr-3.5 shadow-[var(--cs-shadow-sm)] transition-[border-color,box-shadow] duration-150 hover:border-cs-accent hover:shadow-[var(--cs-shadow-md)] sm:pr-4"
          >
            <span className="cs-data rounded-full bg-cs-accent px-2.5 py-1 text-[0.6875rem] font-semibold uppercase leading-none tracking-[0.08em] text-cs-accent-ink">
              New
            </span>
            <BrandMark className="size-6 shrink-0" />
            <span className="min-w-0 truncate text-[0.9375rem] font-medium text-cs-ink">
              CommuteScout Drive<span className="hidden sm:inline"> for iPhone and Android</span>
              <span className="sm:hidden"> app</span>
            </span>
            <ArrowRight aria-hidden className="size-4 shrink-0 text-cs-accent transition-transform duration-150 group-hover:translate-x-0.5" />
          </Link>

          <h1 className="cs-display cs-rise mt-6 [animation-delay:60ms]">
            Live road conditions, straight from the source
          </h1>
          <p className="cs-lede cs-rise mt-6 max-w-[32rem] [animation-delay:120ms]">
            Incidents, closures, chain controls, cameras and wildfires from 53 official sources
            across 37 states, on one live map.
          </p>

          <div className="cs-rise mt-8 flex flex-wrap items-center gap-3 [animation-delay:180ms]">
            <Button
              size="lg"
              nativeButton={false}
              render={
                <Link href="/map" prefetch={false}>
                  Open the live map
                </Link>
              }
            />
            <Button
              size="lg"
              variant="outline"
              nativeButton={false}
              render={
                <Link href="/app" prefetch={false}>
                  Get the app
                </Link>
              }
            />
          </div>

          <p className="cs-rise mt-6 text-sm text-cs-ink-3 [animation-delay:240ms]">
            Free, with no account needed.
          </p>
        </div>

        <div className="cs-rise min-w-0 [animation-delay:120ms] lg:col-span-7 lg:pl-6">
          <figure className="rounded-[calc(var(--cs-radius-lg)+6px)] border border-cs-line bg-cs-surface-2 p-1.5 sm:p-2">
            <div className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line-strong bg-cs-surface shadow-[var(--cs-shadow-md)]">
              {/* One capture per theme. The light one is the LCP image;
                  the dark one is display:none in light mode. */}
              <Image
                src="/shots/live-map-light.webp"
                alt="The CommuteScout live map, zoomed out to show thousands of live incident, closure and road-weather markers."
                width={1600}
                height={939}
                sizes="(min-width: 1024px) 700px, 100vw"
                priority
                className="block h-auto w-full dark:hidden"
              />
              <Image
                src="/shots/live-map-dark.webp"
                alt="The CommuteScout live map on its dark base map, zoomed out to show thousands of live incident, closure and road-weather markers."
                width={1600}
                height={939}
                sizes="(min-width: 1024px) 700px, 100vw"
                className="hidden h-auto w-full dark:block"
              />
            </div>
          </figure>
        </div>
      </div>
    </section>
  );
}
