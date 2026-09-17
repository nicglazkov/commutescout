import type { Metadata } from "next";
import Link from "next/link";
import HeroSection from "@/components/blocks/hero-section-1";
import Features from "@/components/blocks/features-1";
import StatsSection from "@/components/blocks/stats-1";
import { CopyField } from "@/components/copy-field";

// Homepage takes the product-level metadata (Task 7 brief). Description is
// homepage-focused (brand and product overview) and distinct from the map
// page's own description (src/ca_roads_demo/static/map.html, outside site/
// and not editable here) - the two used to be byte-identical, which is
// SERP-cannibalizing duplicate content, and the shared string ran to 202
// chars, well past Google's ~155-char display limit. og:image reuses the
// existing same-origin asset the map page also points at
// (src/ca_roads_demo/static/shots/og.png, served at /static/shots/og.png).
export const metadata: Metadata = {
  title: "CommuteScout: live road conditions, traffic map, and route planner",
  description:
    "CommuteScout tracks live road conditions from 53 official agency feeds across 37 states and plans routes that avoid closures and chain controls.",
  alternates: {
    canonical: "https://commutescout.com/",
  },
  openGraph: {
    title: "CommuteScout: live road conditions, traffic map, and route planner",
    description:
      "CommuteScout tracks live road conditions from 53 official agency feeds across 37 states and plans routes that avoid closures and chain controls.",
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

      {/* Apps band: the phone apps, above the developer band. */}
      <section className="bg-cs-bg">
        <div className="mx-auto max-w-7xl px-6 py-16 md:py-20">
          <div className="grid gap-8 md:grid-cols-2 md:items-center md:gap-12">
            <div>
              <p className="text-sm font-medium uppercase tracking-wider text-cs-ink/50">New</p>
              <h2 className="mt-2 text-balance text-3xl font-medium tracking-tight text-cs-ink md:text-4xl">
                CommuteScout Drive is on iPhone and Android.
              </h2>
              <p className="text-cs-ink/70 mt-4 max-w-md text-balance">
                Turn-by-turn navigation with the same live alerts as this map, spoken before you
                reach them, and one-tap reports from the road. Same account as the website.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 md:justify-end">
              <Link
                href="/app"
                prefetch={false}
                className="rounded-full bg-cs-navy px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-cs-navy/90"
              >
                Get the app
              </Link>
              <a
                href="https://github.com/nicglazkov/commutescout-app/releases/latest"
                className="rounded-full border border-cs-ink/20 px-5 py-2.5 text-sm font-medium text-cs-ink transition-colors hover:bg-white"
              >
                Android APK
              </a>
            </div>
          </div>
        </div>
      </section>

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
