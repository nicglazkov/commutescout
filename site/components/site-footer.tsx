import Image from "next/image";
import Link from "next/link";

// Global site chrome, rendered on every page from app/layout.tsx. Plain
// server-rendered markup (no "use client"): nothing here is interactive.
//
// This is the site's real footer, distinct from the generic, placeholder-
// content footer block vendored at components/blocks/footer-1.tsx (which
// satisfies the "footer" entry in the brief's required vendored block
// types). This component is hand-built to the brief's exact content spec
// rather than composed from that block, and visually borrows its column
// layout.
//
// No email address anywhere on this page, per the brief.
const siteLinks = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

const productLinks = [
  { href: "/map", label: "Open the map" },
  { href: "/watch", label: "Watch areas" },
  { href: "/data-sources", label: "Data sources" },
];

const resourceLinks = [
  { href: "https://github.com/nicglazkov/commutescout", label: "GitHub" },
  { href: "/developers", label: "Developers" },
  { href: "/mcp", label: "MCP server" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
];

// Nic's other public projects. The same strip closes every site in the
// family, so a visitor on any one of them can find the rest.
const siblingProjects = [
  { href: "https://nicglazkov.github.io/switchboard/", label: "Switchboard" },
  { href: "https://chalkboard.studio", label: "Chalkboard" },
  { href: "https://getfiberwatch.com", label: "FiberWatch" },
  { href: "https://nicglazkov.github.io/outagewatch/", label: "OutageWatch" },
  { href: "https://nicglazkov.github.io/chaincheck/", label: "ChainCheck" },
  { href: "https://nicglazkov.github.io/highway-radar-sabre-plus/", label: "SABRE Plus" },
];

const linkColumns = [
  { name: "Site", links: siteLinks },
  { name: "Product", links: productLinks },
  { name: "Resources", links: resourceLinks },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-cs-line bg-cs-navy text-cs-ink">
      <div className="mx-auto max-w-7xl px-6 pb-10 pt-16">
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-4 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div className="col-span-2 sm:col-span-1">
            <Link
              href="/"
              prefetch={false}
              className="flex items-center gap-2.5"
              aria-label="CommuteScout home"
            >
              <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8 rounded-md" />
              <span className="font-display text-base font-extrabold tracking-[-0.02em]">CommuteScout</span>
            </Link>
            <p className="mt-4 max-w-[30ch] text-sm leading-relaxed text-cs-muted">
              Live road conditions read from official state transportation agency feeds.
            </p>
          </div>

          {linkColumns.map((column) => (
            <div key={column.name}>
              <span className="eyebrow">{column.name}</span>
              <ul className="mt-4 space-y-3">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      prefetch={false}
                      className="text-sm text-cs-ink/75 transition-colors hover:text-cs-ink"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col gap-3 border-t border-cs-line pt-6 sm:flex-row sm:items-baseline sm:gap-6">
          <a href="https://nicglazkov.github.io/" className="eyebrow shrink-0 transition-colors hover:text-cs-ink">
            More from Nic
          </a>
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            {siblingProjects.map((p) => (
              <li key={p.href}>
                <a href={p.href} className="text-cs-ink/75 transition-colors hover:text-cs-sky">
                  {p.label}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-6 flex flex-col gap-2 border-t border-cs-line pt-6 text-sm text-cs-muted sm:flex-row sm:justify-between">
          <p>
            Data from CHP, Caltrans, and the state DOTs listed on the{" "}
            <Link
              href="/data-sources"
              prefetch={false}
              className="underline underline-offset-2 hover:text-cs-ink"
            >
              data sources page
            </Link>
            .
          </p>
          <p className="font-mono text-xs">&copy; {new Date().getFullYear()} CommuteScout</p>
        </div>
      </div>
    </footer>
  );
}
