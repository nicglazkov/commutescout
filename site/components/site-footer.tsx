import Link from "next/link";
import { BrandMark } from "@/components/brand/brand-mark";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";

// Global site chrome, rendered on every page from app/layout.tsx. Plain
// server-rendered markup: nothing here is interactive. Every route the
// site has is reachable from here, including the ones the header keeps
// out of its row (/plugins, /about, /contact, the legal pages).
type FooterLink = { href: string; label: string; external?: boolean };

const columns: { name: string; links: FooterLink[] }[] = [
  {
    name: "Product",
    links: [
      { href: "/map", label: "Live map" },
      { href: "/watch", label: "Watch areas" },
      { href: "/app", label: "Get the app" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    name: "Developers",
    links: [
      { href: "/developers", label: "REST API" },
      { href: "/mcp", label: "MCP server" },
      { href: "/plugins", label: "Plugins" },
      { href: "/marketplace", label: "Marketplace" },
      { href: "/data-sources", label: "Data sources" },
    ],
  },
  {
    name: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/contact", label: "Contact" },
      { href: "https://github.com/nicglazkov/commutescout", label: "GitHub", external: true },
    ],
  },
  {
    name: "Legal",
    links: [
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
    ],
  },
];

const linkClass =
  "text-sm text-cs-ink-2 transition-colors duration-150 hover:text-cs-ink";

export function SiteFooter() {
  return (
    <footer className="border-t border-cs-line bg-cs-surface">
      <div className="cs-container pb-10 pt-14 md:pt-16">
        <div className="grid gap-x-8 gap-y-10 md:grid-cols-12">
          <div className="md:col-span-4">
            <Link href="/" prefetch={false} className="inline-flex items-center gap-2.5">
              <BrandMark className="size-7" />
              <span className="text-[0.975rem] font-semibold tracking-[-0.01em] text-cs-ink">CommuteScout</span>
            </Link>
            <p className="mt-4 max-w-[30ch] text-sm leading-relaxed text-cs-ink-2">
              Live road conditions read from official agency feeds. Open source, MIT licensed.
            </p>
            <p className="mt-5 inline-flex items-center gap-2 rounded-full border border-cs-line px-3 py-1.5 text-xs text-cs-ink-2">
              <span aria-hidden className="size-1.5 rounded-full bg-cs-ok" />
              <span className="cs-data">
                {AGENCY_FEED_COUNT} feeds, {STATE_COUNT} states
              </span>
            </p>
          </div>

          <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-4 md:col-span-8">
            {columns.map((col) => (
              <div key={col.name}>
                <h2 className="text-[0.8125rem] font-medium text-cs-ink">{col.name}</h2>
                <ul className="mt-4 space-y-3">
                  {col.links.map((l) => (
                    <li key={l.href}>
                      {l.external ? (
                        <a href={l.href} className={linkClass}>
                          {l.label}
                        </a>
                      ) : (
                        <Link href={l.href} prefetch={false} className={linkClass}>
                          {l.label}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-14 flex flex-col gap-3 border-t border-cs-line pt-6 text-[0.8125rem] leading-relaxed text-cs-ink-3 md:flex-row md:items-start md:justify-between">
          <p className="max-w-[72ch]">
            Data from state transportation agencies, highway patrols, the National Weather Service
            and national wildfire feeds, listed on the{" "}
            <Link href="/data-sources" prefetch={false} className="underline underline-offset-2 hover:text-cs-ink">
              data sources page
            </Link>
            . Not affiliated with any government agency. Check your state&rsquo;s 511 before you
            drive.
          </p>
          <p className="shrink-0">&copy; {new Date().getFullYear()} CommuteScout</p>
        </div>
      </div>
    </footer>
  );
}
