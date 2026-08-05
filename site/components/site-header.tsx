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
      {/* Below sm (640px) this is two rows: row 1 is a plain flex row
          (brand left, CTA right); row 2 is nav, pushed onto its own line
          by flex-col + gap on this wrapper. At sm+ it collapses back to
          the original single row: the inner div goes `contents` (removes
          itself from layout without unmounting its children), so brand
          and the CTA rejoin this row as ordinary flex siblings of nav,
          reordered into brand/nav/CTA via sm:order-*.
          This replaces an earlier version that just let nav
          overflow-x-auto scroll horizontally at any narrow width: at
          375px that produced a ~25px-wide scroll strip with no visible
          scrollbar, hiding 3 of 4 destinations with no discoverable way
          to reach them. Two rows keeps every destination visible and
          tappable without scrolling. Mirrors the same restructuring on
          the legacy .topbar (src/ca_roads_demo/static/map.html): the
          Live map link there also moved from inside <nav> to a topbar-
          level sibling for the same reason - it needs to sit on row 1
          next to the brand, not get swept into row 2 with the other
          four links. */}
      <div className="mx-auto flex max-w-7xl flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center sm:gap-6 sm:px-6 sm:py-3">
        <div className="flex items-center justify-between gap-3 sm:contents">
          <Link
            href="/"
            prefetch={false}
            className="flex shrink-0 items-center gap-2.5"
            aria-label="CommuteScout home"
          >
            <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8 rounded-md" />
            <span className="text-base font-semibold text-white">CommuteScout</span>
          </Link>

          <Link
            href="/map"
            prefetch={false}
            className="shrink-0 rounded-full bg-cs-sky px-4 py-2 text-sm font-medium text-white whitespace-nowrap transition-colors hover:bg-cs-sky/90 sm:order-3"
          >
            Live map
          </Link>
        </div>

        {/* grid-cols-4 below sm: one row, four equal columns, every
            link a >=40px (min-h-10) tap target - full width, evenly
            distributed, no scrolling. At sm+, back to the original
            inline row (min-w-0 lets this flex-1 item shrink below its
            content's natural width, a classic flexbox gotcha: flex
            items default to min-width:auto). */}
        <nav className="grid grid-cols-4 gap-1 sm:order-2 sm:flex sm:min-w-0 sm:flex-1 sm:items-center sm:gap-1">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                prefetch={false}
                aria-current={isActive ? "page" : undefined}
                className={`flex min-h-10 items-center justify-center rounded-lg px-0.5 text-center text-[11px] whitespace-normal transition-colors sm:min-h-0 sm:shrink-0 sm:justify-start sm:px-3 sm:py-2 sm:text-left sm:text-sm sm:whitespace-nowrap ${
                  isActive ? "text-white" : "text-white/70 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
