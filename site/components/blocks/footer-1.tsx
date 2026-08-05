import Image from "next/image";
import Link from "next/link";

// Source: Tailark OSS registry, Dusk kit, dusk-footer-1
// (https://oss.tailark.com/r/dusk-footer-1.json).
//
// Adapted from upstream:
// - LogoIcon swapped for /logo.svg, served by the Python app at the site
//   root (same pattern as components/site-header.tsx).
// - The newsletter signup form (Label + Input, dusk-input/dusk-label) was
//   dropped entirely, not just recolored: no page in this site collects or
//   displays an email address, and there is no backend to receive a
//   subscription.
// - text-muted-foreground/hover:text-primary replaced with --cs-* tokens.
// - Link groups are still Tailark's generic placeholders. The site's real,
//   global footer with CommuteScout's actual sitemap is
//   components/site-footer.tsx, hand-built to that exact spec rather than
//   configured through this block.
const footerLinks = [
  {
    name: "Product",
    links: [
      { href: "#", label: "Link placeholder" },
      { href: "#", label: "Link placeholder" },
      { href: "#", label: "Link placeholder" },
    ],
  },
  {
    name: "Company",
    links: [
      { href: "#", label: "Link placeholder" },
      { href: "#", label: "Link placeholder" },
      { href: "#", label: "Link placeholder" },
    ],
  },
  {
    name: "Legal",
    links: [
      { href: "#", label: "Link placeholder" },
      { href: "#", label: "Link placeholder" },
    ],
  },
];

export default function Footer() {
  return (
    <footer>
      <div className="mx-auto max-w-7xl space-y-16 px-6 pb-16 pt-32">
        <div className="grid grid-cols-2 gap-x-3 gap-y-12 sm:grid-cols-4 lg:grid-cols-5">
          <div className="max-lg:col-span-full">
            <Link href="/" prefetch={false} aria-label="go home">
              <Image src="/logo.svg" alt="CommuteScout" width={32} height={32} className="h-8 w-8" />
            </Link>
          </div>

          {footerLinks.map((linksGroup, index) => (
            <div key={index}>
              <span className="text-sm font-medium">{linksGroup.name}</span>
              <ul className="mt-4 list-inside space-y-4">
                {linksGroup.links.map((link, linkIndex) => (
                  <li key={linkIndex}>
                    <Link
                      href={link.href}
                      prefetch={false}
                      className="hover:text-cs-sky text-cs-ink/60 text-sm duration-150"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-16">
          <span className="text-cs-ink/60 block text-sm">Placeholder copyright line.</span>
        </div>
      </div>
    </footer>
  );
}
