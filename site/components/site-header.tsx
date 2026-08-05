"use client";

import Image from "next/image";
// Every Link in site/ is rendered with prefetch={false}. Navigation here is
// a full page load by design (see the site route table in
// src/ca_roads_demo/app.py), and the server deliberately does not serve the
// RSC segment-tree payloads (__next._tree.txt) that next/link prefetches on
// viewport entry. Leaving the default prefetch on produces a 404 for every
// nav link on every page load; prefetch={false} keeps the console clean.
import Link from "next/link";
import { usePathname } from "next/navigation";

// Global site chrome, rendered on every page from app/layout.tsx. A logo,
// four nav links, and a primary CTA link are not interactive enough to need
// much client JS, but marking the current page's nav link requires knowing
// the current path, so this is "use client" and reads it with usePathname()
// (see node_modules/next/dist/docs/01-app/03-api-reference/02-components/
// link.md, "Checking active links"). During the static export build, each
// route is still prerendered in its own URL context, so usePathname()
// resolves correctly in the exported HTML too, not just after hydration.
// This deliberately does not use the vendored Button primitive
// (components/ui/button.tsx), which wraps a Base UI client component.
//
// Visually rhymes with the map app's .topbar (src/ca_roads_demo/static/
// map.html): navy bar, muted white nav links, brighter white on hover, and
// the same nav destination set and order (Watch areas, Data sources,
// Developers, Pricing, then Live map as a CTA button) so the header reads
// as one component across this site and the legacy static app pages.
const navLinks = [
  { href: "/watch", label: "Watch areas" },
  { href: "/data-sources", label: "Data sources" },
  { href: "/mcp", label: "Developers" },
  { href: "/pricing", label: "Pricing" },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="bg-cs-navy">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
        <Link
          href="/"
          prefetch={false}
          className="flex shrink-0 items-center gap-2.5"
          aria-label="CommuteScout home"
        >
          <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8 rounded-md" />
          <span className="text-base font-semibold text-white">CommuteScout</span>
        </Link>

        {/* min-w-0 lets this flex-1 item shrink below its content's natural
            width so overflow-x-auto can actually kick in on a narrow
            viewport, instead of the flex row just overflowing the header
            (a classic flexbox gotcha: flex items default to min-width:
            auto). shrink-0 + whitespace-nowrap on each link keeps them from
            wrapping mid-word as the scroll area narrows. The
            scrollbar-hiding utilities rhyme with the map app's .topbar nav
            on mobile (src/ca_roads_demo/static/map.html), which uses the
            same overflow-x:auto + hidden-scrollbar pattern for the same
            reason: five nav destinations do not fit a 375px header. */}
        <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                prefetch={false}
                aria-current={isActive ? "page" : undefined}
                className={`shrink-0 rounded-lg px-3 py-2 text-sm whitespace-nowrap transition-colors ${
                  isActive ? "text-white" : "text-white/70 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <Link
          href="/map"
          prefetch={false}
          className="shrink-0 rounded-full bg-cs-sky px-4 py-2 text-sm font-medium text-white whitespace-nowrap transition-colors hover:bg-cs-sky/90"
        >
          Live map
        </Link>
      </div>
    </header>
  );
}
