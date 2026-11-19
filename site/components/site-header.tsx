"use client";

// Every Link in site/ is rendered with prefetch={false}. Navigation here is
// a full page load by design (see the site route table in
// src/ca_roads_demo/app.py), and the server deliberately does not serve the
// RSC segment-tree payloads (__next._tree.txt) that next/link prefetches on
// viewport entry. Leaving the default prefetch on produces a 404 for every
// nav link on every page load; prefetch={false} keeps the console clean.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, ChevronDown, Menu, Plug, Puzzle, X } from "lucide-react";
import { BrandMark } from "@/components/brand/brand-mark";
import { ThemeToggle } from "@/components/brand/theme-toggle";

// Global site chrome, rendered on every page from app/layout.tsx.
//
// tests/test_nav_cohesion.py pins this header's links against the legacy
// app pages (map/watch/trip/admin.html): exactly these destinations, these
// labels, in this order, one "Live map" link to /map, and the logo as the
// only link home. The three developer destinations sit inside the
// Developers menu, which keeps their order (/developers, /mcp,
// /marketplace) and their exact link text; each item's description is a
// sibling of its link, not inside it, so the link text stays the label.
// Every link is in the server-rendered HTML whether or not a menu is open.
//
// One <nav> serves both layouts. From lg (1024px) it is the inline row
// with the Developers popover; below lg it is a sheet opened by the Menu
// button, with the developer items listed in place.
type NavItem = { href: string; label: string };
type DevItem = NavItem & { note: string; icon: typeof BookOpen };

const before: NavItem[] = [
  { href: "/watch", label: "Watch areas" },
  { href: "/data-sources", label: "Data sources" },
];
const developers: DevItem[] = [
  {
    href: "/developers",
    label: "Developers",
    note: "REST API reference, keys and daily limits",
    icon: BookOpen,
  },
  {
    href: "/mcp",
    label: "MCP server",
    note: "Connect Claude, ChatGPT, Cursor or any MCP client",
    icon: Plug,
  },
  {
    href: "/marketplace",
    label: "Marketplace",
    note: "Plugins that add alerts to the map and the apps",
    icon: Puzzle,
  },
];
const after: NavItem[] = [
  { href: "/app", label: "Get the app" },
  { href: "/pricing", label: "Pricing" },
];

const DEV_PATHS = new Set(["/developers", "/mcp", "/marketplace", "/plugins"]);

const topLink =
  "flex min-h-11 items-center rounded-[var(--cs-radius-md)] px-3 text-[0.9375rem] text-cs-ink-2 transition-colors duration-150 hover:bg-cs-surface-2 hover:text-cs-ink aria-[current=page]:text-cs-ink aria-[current=page]:font-medium lg:min-h-9 lg:text-sm";

export function SiteHeader() {
  const pathname = usePathname();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const devRef = useRef<HTMLLIElement>(null);
  const devButton = useRef<HTMLButtonElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);
  // When hover just opened the menu, the click that follows (a mouse user
  // aiming at the button) must not close it again.
  const hoverOpenedAt = useRef(0);

  const closeDev = useCallback((focus = false) => {
    setDevOpen(false);
    if (focus) devButton.current?.focus();
  }, []);

  // Escape closes whatever is open; a click outside closes the popover.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      if (devOpen) closeDev(true);
      else if (sheetOpen) setSheetOpen(false);
    }
    function onPointer(e: PointerEvent) {
      if (devOpen && devRef.current && !devRef.current.contains(e.target as Node)) closeDev();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [devOpen, sheetOpen, closeDev]);

  // Hover intent for mouse users on the desktop row; touch and keyboard
  // use the button.
  const hoverOpen = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse" || !window.matchMedia("(min-width: 1024px)").matches) return;
    window.clearTimeout(closeTimer.current);
    if (!devOpen) hoverOpenedAt.current = e.timeStamp;
    setDevOpen(true);
  };
  const hoverClose = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse") return;
    closeTimer.current = window.setTimeout(() => setDevOpen(false), 160);
  };

  const devActive = DEV_PATHS.has(pathname);
  const current = (href: string) => (pathname === href ? "page" : undefined);

  return (
    <header className="sticky top-0 z-40 border-b border-cs-line bg-[color-mix(in_srgb,var(--cs-bg)_86%,transparent)] backdrop-blur-md backdrop-saturate-150">
      <div className="cs-container flex h-16 items-center gap-6">
        <Link
          href="/"
          prefetch={false}
          aria-label="CommuteScout home"
          className="-ml-1 flex shrink-0 items-center gap-2.5 rounded-[var(--cs-radius-md)] px-1 py-1"
        >
          <BrandMark className="size-7" />
          <span className="text-[0.975rem] font-semibold tracking-[-0.01em] text-cs-ink">CommuteScout</span>
        </Link>

        <nav
          id="site-nav"
          aria-label="Site"
          className={`${
            sheetOpen ? "block" : "hidden"
          } absolute inset-x-0 top-16 max-h-[calc(100dvh-4rem)] overflow-y-auto border-b border-cs-line bg-cs-bg px-5 pb-6 pt-2 shadow-[var(--cs-shadow-md)] lg:static lg:block lg:max-h-none lg:flex-1 lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none`}
        >
          <ul className="flex flex-col lg:flex-row lg:items-center lg:gap-0.5">
            {before.map((l) => (
              <li key={l.href} className="border-b border-cs-line lg:border-0">
                <Link href={l.href} prefetch={false} aria-current={current(l.href)} className={topLink}>
                  {l.label}
                </Link>
              </li>
            ))}

            <li
              ref={devRef}
              className="relative border-b border-cs-line py-2 lg:border-0 lg:py-0"
              onPointerEnter={hoverOpen}
              onPointerLeave={hoverClose}
            >
              <button
                ref={devButton}
                type="button"
                aria-expanded={devOpen}
                aria-controls="dev-menu"
                onClick={(e) => {
                  if (devOpen && e.timeStamp - hoverOpenedAt.current < 600) return;
                  setDevOpen((o) => !o);
                }}
                className={`hidden items-center gap-1 lg:inline-flex ${topLink} ${devActive ? "font-medium text-cs-ink" : ""}`}
              >
                Developers
                <ChevronDown
                  aria-hidden
                  className={`size-3.5 text-cs-ink-3 transition-transform duration-200 ${devOpen ? "rotate-180" : ""}`}
                />
              </button>
              <p className="cs-eyebrow px-3 pb-1 pt-2 lg:hidden">For developers</p>

              <div
                id="dev-menu"
                className={`lg:absolute lg:left-1/2 lg:top-full lg:w-[23rem] lg:-translate-x-1/2 lg:pt-2 lg:transition-[opacity,transform,visibility] lg:duration-200 lg:ease-[var(--cs-ease)] ${
                  devOpen
                    ? "lg:visible lg:translate-y-0 lg:opacity-100"
                    : "lg:invisible lg:-translate-y-1 lg:opacity-0"
                }`}
              >
                <ul className="lg:rounded-[var(--cs-radius-lg)] lg:border lg:border-cs-line lg:bg-cs-surface lg:p-1.5 lg:shadow-[var(--cs-shadow-md)]">
                  {developers.map(({ href, label, note, icon: Icon }) => (
                    <li
                      key={href}
                      className="group relative flex gap-3 rounded-[var(--cs-radius-md)] px-3 py-2.5 transition-colors duration-150 hover:bg-cs-surface-2 has-[a:focus-visible]:bg-cs-surface-2"
                    >
                      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-[var(--cs-radius-sm)] border border-cs-line bg-cs-surface text-cs-ink-2 transition-colors group-hover:text-cs-accent">
                        <Icon aria-hidden className="size-4" strokeWidth={1.75} />
                      </span>
                      <span className="min-w-0">
                        <Link
                          href={href}
                          prefetch={false}
                          aria-current={current(href)}
                          onClick={() => setDevOpen(false)}
                          className="text-sm font-medium text-cs-ink outline-none after:absolute after:inset-0 after:rounded-[var(--cs-radius-md)] focus-visible:after:outline-2 focus-visible:after:outline-cs-accent aria-[current=page]:text-cs-accent"
                        >
                          {label}
                        </Link>
                        <span className="mt-0.5 block text-[0.8125rem] leading-snug text-cs-ink-3">{note}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </li>

            {after.map((l) => (
              <li key={l.href} className="border-b border-cs-line last:border-0 lg:border-0">
                <Link href={l.href} prefetch={false} aria-current={current(l.href)} className={topLink}>
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-1.5 lg:ml-0">
          <ThemeToggle />
          <Link
            href="/map"
            prefetch={false}
            className="ml-1 inline-flex h-9 items-center whitespace-nowrap rounded-[var(--cs-radius-md)] bg-cs-accent px-3.5 text-sm font-medium text-cs-accent-ink shadow-[var(--cs-shadow-sm)] transition-colors duration-150 hover:bg-cs-accent-hover"
          >
            Live map
          </Link>
          <button
            type="button"
            aria-expanded={sheetOpen}
            aria-controls="site-nav"
            onClick={() => setSheetOpen((o) => !o)}
            className="-mr-2 inline-flex size-11 items-center justify-center rounded-[var(--cs-radius-md)] text-cs-ink transition-colors hover:bg-cs-surface-2 lg:hidden"
          >
            <span className="sr-only">{sheetOpen ? "Close menu" : "Menu"}</span>
            {sheetOpen ? <X aria-hidden className="size-5" /> : <Menu aria-hidden className="size-5" />}
          </button>
        </div>
      </div>
    </header>
  );
}
