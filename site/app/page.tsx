import type { Metadata } from "next";
import Link from "next/link";
import HeroSection from "@/components/blocks/hero-section-1";
import Features from "@/components/blocks/features-1";
import StatsSection from "@/components/blocks/stats-1";
import { CopyField } from "@/components/copy-field";

// Homepage takes the product-level metadata (Task 7 brief). Description
// matches the map page's current one (src/ca_roads_demo/static/map.html);
// og:image reuses the existing same-origin asset the map page also points
// at (src/ca_roads_demo/static/shots/og.png, served at /static/shots/og.png).
export const metadata: Metadata = {
  title: "CommuteScout: live road conditions, traffic map, and route planner",
  description:
    "Live traffic map and route planner across 38 states: incidents, lane closures, chain controls, wildfires, live highway cameras, and message signs from official DOT feeds. Deepest coverage in California.",
  alternates: {
    canonical: "https://commutescout.com/",
  },
  openGraph: {
    title: "CommuteScout: live road conditions, traffic map, and route planner",
    description:
      "Live traffic map and route planner across 38 states: incidents, lane closures, chain controls, wildfires, live highway cameras, and message signs from official DOT feeds. Deepest coverage in California.",
    // The brief pins this to exactly "https://commutescout.com/" (trailing
    // slash). Next 16's metadata resolver unconditionally normalizes a
    // root-path absolute URL to origin-only (see resolveAbsoluteUrlWithPathname
    // in next/dist/lib/metadata/resolvers/resolve-url.js: for a URL whose
    // pathname is exactly "/", it emits `result.origin`, dropping the
    // slash, with no metadata-level opt-out). Passing it through `other`
    // instead avoids that, but emits `<meta name="og:url">` rather than
    // the OG-spec `property="og:url"` every other og: tag on this page
    // uses, which is worse. Keeping the framework-resolved,
    // spec-correct tag: same resource, slash-insensitive.
    url: "https://commutescout.com/",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

const MCP_URL = "https://mcp.commutescout.com/mcp";

export default function Home() {
  return (
    <>
      <HeroSection />
      <Features />
      <StatsSection />

      {/* Developer band. Not a vendored Tailark block: none of the six
          required block types (hero, feature grid, stat band, pricing,
          FAQ/content, footer) fit a one-off connector-URL callout, so this
          is page-owned markup, styled to match the navy header/footer
          bands. */}
      <section className="bg-cs-navy text-white">
        <div className="mx-auto max-w-7xl px-6 py-16 md:py-20">
          <div className="grid gap-8 md:grid-cols-2 md:items-center md:gap-12">
            <div>
              <h2 className="text-balance text-3xl font-medium tracking-tight md:text-4xl">
                Bring live roads to your assistant.
              </h2>
              <p className="text-white/70 mt-4 max-w-md text-balance">
                Connect any MCP-compatible assistant to the same live feeds the map
                reads from.
              </p>
            </div>
            <div className="space-y-4">
              <CopyField value={MCP_URL} />
              <Link
                href="/mcp"
                prefetch={false}
                className="inline-flex items-center gap-1.5 text-sm text-white/70 underline underline-offset-4 transition-colors hover:text-white"
              >
                View the MCP docs
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Global footer: rendered once from app/layout.tsx via
          <SiteFooter/>, not repeated here. */}
    </>
  );
}
