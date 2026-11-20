import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Database, Map as MapIcon } from "lucide-react";
import { BrandMark } from "@/components/brand/brand-mark";

// The 404 page. Without this file the static export shipped Next's default
// "404: This page could not be found." block, which brings its own black and
// white styles and ignores the site's colors. The Starlette app serves the
// exported 404.html for every unknown path (see not_found in
// src/ca_roads_demo/app.py), so this is what a mistyped link lands on.
export const metadata: Metadata = {
  title: "Page not found - CommuteScout",
  robots: { index: false },
};

const destinations = [
  { href: "/map", label: "Live map", note: "Incidents, closures and cameras near you", icon: MapIcon },
  { href: "/app", label: "Get the app", note: "CommuteScout Drive for iPhone and Android", icon: null },
  { href: "/data-sources", label: "Data sources", note: "Which agency feeds each state uses", icon: Database },
];

export default function NotFound() {
  return (
    <section className="cs-container pb-24 pt-14 md:pb-32 md:pt-20">
      <div className="grid items-center gap-12 lg:grid-cols-12">
        <div className="lg:col-span-6">
          {/* The code is the page's first, largest mark: a mono numeral,
              so it reads as a status code, not a headline. */}
          <p className="cs-data flex items-baseline gap-4 leading-none">
            <span className="sr-only">Error</span>
            <span className="text-[clamp(5.5rem,13vw,9.5rem)] font-medium tracking-[-0.07em] text-cs-accent">404</span>
            <span aria-hidden className="cs-eyebrow">Not found</span>
          </p>
          <h1 className="cs-display mt-6">This page isn&rsquo;t here</h1>
          <p className="cs-lede mt-6 max-w-[30rem]">
            The link may be old or mistyped. These are good places to pick up from.
          </p>
        </div>
        <div className="lg:col-span-5 lg:col-start-8">
          <ul className="grid gap-3">
            {destinations.map((d) => (
              <li key={d.href}>
                <Link
                  href={d.href}
                  prefetch={false}
                  className="group flex items-center gap-4 rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-4 shadow-[var(--cs-shadow-sm)] transition-[border-color,box-shadow,transform] duration-150 hover:-translate-y-0.5 hover:border-cs-accent hover:shadow-[var(--cs-shadow-md)] sm:p-5 motion-reduce:hover:translate-y-0"
                >
                  <span className="flex size-12 shrink-0 items-center justify-center rounded-[var(--cs-radius-md)] bg-cs-accent-soft text-cs-accent">
                    {d.icon ? <d.icon aria-hidden className="size-6" strokeWidth={1.75} /> : <BrandMark className="size-8" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[1.0625rem] font-semibold tracking-[-0.01em] text-cs-ink">{d.label}</span>
                    <span className="mt-0.5 block text-sm text-cs-ink-2">{d.note}</span>
                  </span>
                  <span
                    aria-hidden="true"
                    className="flex size-9 shrink-0 items-center justify-center rounded-full border border-cs-line-strong text-cs-ink-2 transition-colors duration-150 group-hover:border-cs-accent group-hover:bg-cs-accent group-hover:text-cs-accent-ink"
                  >
                    <ArrowRight className="size-4" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-6 text-sm text-cs-ink-2">
            Or go to the{" "}
            <Link href="/" prefetch={false} className="cs-link">
              home page
            </Link>
            .
          </p>
        </div>
      </div>
    </section>
  );
}
