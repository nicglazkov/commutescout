import Image from "next/image";
import Link from "next/link";

// Global site chrome, rendered on every page from app/layout.tsx. Plain
// server-rendered markup (no "use client"): a logo, four nav links, and a
// primary CTA link are not interactive enough to need any client JS, so
// this deliberately does not use the vendored Button primitive
// (components/ui/button.tsx), which wraps a Base UI client component.
//
// Visually rhymes with the map app's .topbar (src/ca_roads_demo/static/
// map.html): navy bar, muted white nav links, brighter white on hover.
const navLinks = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader() {
  return (
    <header className="bg-cs-navy">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
        <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="CommuteScout home">
          <Image src="/logo.svg" alt="" width={32} height={32} className="h-8 w-8 rounded-md" />
          <span className="text-base font-semibold text-white">CommuteScout</span>
        </Link>

        <nav className="flex flex-1 items-center gap-1">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-lg px-3 py-2 text-sm text-white/70 transition-colors hover:text-white"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <Link
          href="/map"
          className="rounded-full bg-cs-sky px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-cs-sky/90"
        >
          Open the map
        </Link>
      </div>
    </header>
  );
}
