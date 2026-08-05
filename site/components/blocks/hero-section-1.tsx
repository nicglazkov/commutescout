import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

// Source: Tailark OSS registry, Dusk kit, dusk-hero-section-1
// (https://oss.tailark.com/r/dusk-hero-section-1.json).
//
// Adapted from upstream:
// - Dropped the block's own embedded <HeroHeader /> nav: the site already
//   renders one global header (components/site-header.tsx) in app/layout.tsx,
//   so a second nav bar baked into the hero would compete with it.
// - Dropped the "trusted by" third-party logo strip (Spotify, Supabase,
//   Hulu, etc.) and the screenshot mockup: both were stock Tailark content
//   with no CommuteScout equivalent and no product screenshot asset exists
//   yet. A future page task can add a real screenshot here.
// - text-muted-foreground replaced with text-cs-ink/60; the rest of the
//   text inherits the page's --cs-ink color from the body rule in
//   app/globals.css, same as upstream relied on a global text-foreground.
// - Copy and hrefs are placeholders ("#"); the page that composes this
//   block owns real copy and links.
export default function HeroSection() {
  return (
    <section className="overflow-hidden">
      <div className="relative pt-24 md:pt-36">
        <div className="mx-auto max-w-7xl">
          <div className="px-6 text-center sm:mx-auto lg:mr-auto lg:mt-0">
            <Link
              href="#"
              className="group mx-auto flex w-fit items-center gap-3 rounded-full bg-cs-paper p-1 pl-4 ring-1 ring-cs-line transition-colors duration-300"
            >
              <span className="text-sm font-medium">New:</span>
              <span className="text-cs-ink/60 text-sm">Announcement placeholder</span>
              <div className="size-6 overflow-hidden rounded-full duration-500">
                <div className="flex w-12 -translate-x-1/2 duration-500 ease-in-out group-hover:translate-x-0">
                  <span className="flex size-6">
                    <ArrowRight className="m-auto size-3" />
                  </span>
                  <span className="flex size-6">
                    <ArrowRight className="m-auto size-3" />
                  </span>
                </div>
              </div>
            </Link>

            <h1 className="mx-auto mt-8 max-w-4xl text-balance text-5xl font-medium tracking-tight md:text-6xl lg:mt-12 xl:text-7xl">
              Headline placeholder
            </h1>
            <p className="text-cs-ink/60 mx-auto mt-4 max-w-2xl text-balance md:text-lg">
              Subheadline placeholder copy goes here, one or two sentences describing the
              product.
            </p>

            <div className="mt-6 flex flex-col items-center justify-center gap-2 pb-16 md:flex-row md:pb-24">
              <Button nativeButton={false} render={<Link href="#"><span className="text-nowrap">Primary action</span></Link>} />
              <Button
                variant="ghost"
                nativeButton={false}
                render={<Link href="#"><span className="text-nowrap">Secondary action</span></Link>}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
