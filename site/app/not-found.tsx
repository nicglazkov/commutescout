import type { Metadata } from "next";
import Link from "next/link";

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
  { href: "/map", label: "Live map", note: "Incidents, closures and cameras near you" },
  { href: "/app", label: "Get the app", note: "CommuteScout Drive for iPhone and Android" },
  { href: "/data-sources", label: "Data sources", note: "Which agency feeds each state uses" },
];

export default function NotFound() {
  return (
    <section className="cs-container pb-24 pt-16 md:pb-32 md:pt-24">
      <div className="grid gap-12 lg:grid-cols-12">
        <div className="lg:col-span-6">
          <p className="cs-eyebrow">Error 404</p>
          <h1 className="cs-display mt-5">This page isn&rsquo;t here.</h1>
          <p className="cs-lede mt-6 max-w-[30rem]">
            The link may be old or mistyped. These are good places to pick up from.
          </p>
        </div>
        <div className="lg:col-span-5 lg:col-start-8 lg:pt-10">
          <ul className="border-t border-cs-line">
            {destinations.map((d) => (
              <li key={d.href} className="border-b border-cs-line">
                <Link href={d.href} prefetch={false} className="group flex items-center justify-between gap-4 py-5">
                  <span>
                    <span className="block font-medium text-cs-ink group-hover:text-cs-accent">{d.label}</span>
                    <span className="mt-0.5 block text-sm text-cs-ink-3">{d.note}</span>
                  </span>
                  <span aria-hidden="true" className="text-cs-ink-3 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-cs-accent">
                    &rarr;
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
