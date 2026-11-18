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
import { useState } from "react";

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
  { href: "/developers", label: "Developers" },
  { href: "/mcp", label: "MCP server" },
  { href: "/marketplace", label: "Marketplace" },
  { href: "/app", label: "Get the app" },
  { href: "/pricing", label: "Pricing" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="border-b border-cs-line bg-cs-navy/80">
      {/* Below sm (640px) this is one row: brand left, then the Live map
          CTA and a Menu button that opens the nav underneath. At sm+ the
          inner div goes `contents` (removes itself from layout without
          unmounting its children), so brand and the CTA rejoin this row
          as ordinary flex siblings of nav, reordered into brand/nav/CTA
          via sm:order-*, and the nav is always shown.
          Earlier versions either scrolled the nav sideways (hiding most
          links with no visible scrollbar) or always showed it as a grid
          under the brand row. With six links that grid took two more
          rows and the header grew to about 190 px on a phone. The Menu
          button keeps every link one tap away for 56 px of header. */}
      <div className="mx-auto flex max-w-7xl flex-col px-4 sm:min-h-16 sm:flex-row sm:items-center sm:gap-6 sm:px-6">
        <div className="flex h-16 items-center justify-between gap-3 sm:contents">
          <Link
            href="/"
            prefetch={false}
            className="flex shrink-0 items-center gap-2.5"
            aria-label="CommuteScout home"
          >
            <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8 rounded-md" />
            <span className="font-display text-[1.05rem] font-extrabold tracking-[-0.02em] text-cs-ink">CommuteScout</span>
          </Link>

          <div className="flex items-center gap-2 sm:contents">
            <Link
              href="/map"
              prefetch={false}
              className="shrink-0 rounded-[var(--site-radius)] bg-cs-sky px-4 py-2 text-sm font-bold text-cs-on-sky whitespace-nowrap shadow-[0_0_24px_-6px_var(--cs-sky)] transition-colors hover:bg-cs-sky/90 sm:order-3"
            >
              Live map
            </Link>

            <button
              type="button"
              aria-expanded={menuOpen}
              aria-controls="site-nav"
              onClick={() => setMenuOpen((open) => !open)}
              className="flex h-10 w-10 items-center justify-center rounded-lg text-cs-ink/80 transition-colors hover:bg-cs-ink/10 hover:text-cs-ink sm:hidden"
            >
              <span className="sr-only">{menuOpen ? "Close menu" : "Menu"}</span>
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
                {menuOpen ? (
                  <path d="M6 6l12 12M18 6L6 18" />
                ) : (
                  <path d="M4 7h16M4 12h16M4 17h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Below sm: hidden until the Menu button opens it, then a
            two-column list of >=44px tap targets. At sm+ it is always
            the inline row (min-w-0 lets this flex-1 item shrink below its
            content's natural width, a classic flexbox gotcha: flex items
            default to min-width:auto). */}
        <nav
          id="site-nav"
          aria-label="Site"
          className={`${menuOpen ? "grid" : "hidden"} mb-3 grid-cols-2 gap-1 sm:order-2 sm:mb-0 sm:mt-0 sm:flex sm:min-w-0 sm:flex-1 sm:items-center sm:gap-1`}
        >
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                prefetch={false}
                aria-current={isActive ? "page" : undefined}
                className={`relative flex min-h-11 items-center rounded-lg px-3 text-sm font-medium whitespace-nowrap transition-colors hover:bg-cs-ink/5 sm:min-h-0 sm:shrink-0 sm:px-2.5 sm:py-2 sm:hover:bg-transparent ${
                  isActive
                    ? "text-cs-ink sm:after:absolute sm:after:inset-x-2.5 sm:after:-bottom-[13px] sm:after:h-px sm:after:bg-cs-sky"
                    : "text-cs-muted hover:text-cs-ink"
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
