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
  { href: "/mcp", label: "MCP server" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
];

const linkColumns = [
  { name: "Site", links: siteLinks },
  { name: "Product", links: productLinks },
  { name: "Resources", links: resourceLinks },
];

export function SiteFooter() {
  return (
    <footer className="bg-cs-navy text-white">
      <div className="mx-auto max-w-7xl space-y-12 px-6 pb-10 pt-16">
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <Link
              href="/"
              prefetch={false}
              className="flex items-center gap-2.5"
              aria-label="CommuteScout home"
            >
              <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8 rounded-md" />
              <span className="text-base font-semibold">CommuteScout</span>
            </Link>
          </div>

          {linkColumns.map((column) => (
            <div key={column.name}>
              <span className="text-sm font-medium text-white/70">{column.name}</span>
              <ul className="mt-4 space-y-3">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      prefetch={false}
                      className="text-sm text-white/70 transition-colors hover:text-white"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="space-y-2 border-t border-white/10 pt-6 text-sm text-white/60">
          <p>
            Data from CHP, Caltrans, and the state DOTs listed on the{" "}
            <Link
              href="/data-sources"
              prefetch={false}
              className="underline underline-offset-2 hover:text-white"
            >
              data sources page
            </Link>
            .
          </p>
          <p>&copy; {new Date().getFullYear()} CommuteScout</p>
        </div>
      </div>
    </footer>
  );
}
