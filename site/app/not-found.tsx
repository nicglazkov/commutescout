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
    <section className="py-16 md:py-24">
      <div className="mx-auto max-w-2xl px-6">
        <p className="text-cs-sky text-sm font-semibold">404</p>
        <h1 className="text-cs-ink mt-2 text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          This page isn&rsquo;t here
        </h1>
        <p className="text-cs-ink/70 mt-4 text-lg">
          The link may be old or mistyped. These are good places to pick up from:
        </p>
        <ul className="mt-8 divide-y divide-cs-ink/10 border-y border-cs-ink/10">
          {destinations.map((d) => (
            <li key={d.href}>
              <Link
                href={d.href}
                prefetch={false}
                className="hover:bg-cs-ink/[0.03] flex items-center justify-between gap-4 px-1 py-4"
              >
                <span>
                  <span className="text-cs-ink block font-medium">{d.label}</span>
                  <span className="text-cs-ink/60 block text-sm">{d.note}</span>
                </span>
                <span aria-hidden="true" className="text-cs-ink/40">
                  &rarr;
                </span>
              </Link>
            </li>
          ))}
        </ul>
        <p className="text-cs-ink/70 mt-8 text-sm">
          Or go to the{" "}
          <Link href="/" prefetch={false} className="text-cs-sky underline underline-offset-2">
            home page
          </Link>
          .
        </p>
      </div>
    </section>
  );
}
