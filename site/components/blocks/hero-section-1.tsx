import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HeroScene } from "@/components/home/hero-scene";

// The homepage hero. A left-aligned split: the claim, what CommuteScout
// reads, two actions, then a made-up area with three sample events on the
// right. The counts in the lede are pinned by tests/test_snapshot.py
// (test_state_counts_are_current, test_feed_counts_are_current), which
// read this file for "reads N official agency feeds" and "across N states".
export default function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      <div className="cs-container grid items-center gap-12 pb-16 pt-12 md:pb-24 md:pt-20 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          <Link
            href="/app"
            prefetch={false}
            className="group cs-rise inline-flex items-center gap-2 text-[0.8125rem] text-cs-ink-2 transition-colors hover:text-cs-ink"
          >
            <span className="cs-data rounded-[var(--cs-radius-sm)] bg-cs-accent-soft px-1.5 py-0.5 text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-cs-accent">
              New
            </span>
            CommuteScout Drive for iPhone and Android
            <ArrowRight aria-hidden className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
          </Link>

          <h1 className="cs-display cs-rise mt-6 [animation-delay:60ms]">
            Live road conditions, straight from the source.
          </h1>
          <p className="cs-lede cs-rise mt-6 max-w-[34rem] [animation-delay:120ms]">
            CommuteScout reads 53 official agency feeds across 37 states and puts incidents,
            closures, chain controls, cameras and wildfires on one live map.
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

          <p className="cs-rise mt-8 flex items-start gap-2.5 text-sm text-cs-ink-3 [animation-delay:240ms]">
            <span aria-hidden className="relative mt-[7px] flex size-1.5 shrink-0">
              <span className="absolute inset-0 rounded-full bg-cs-ok" />
            </span>
            Every record carries its own source and timestamp. The map is free and needs no account.
          </p>
        </div>

        <div className="lg:col-span-7 lg:pl-6">
          <HeroScene />
        </div>
      </div>
    </section>
  );
}
