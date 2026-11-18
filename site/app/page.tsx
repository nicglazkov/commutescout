import type { Metadata } from "next";
import Link from "next/link";
import HeroSection from "@/components/blocks/hero-section-1";
import AppBand from "@/components/blocks/app-band";
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
      <AppBand />
      <Features />
      <StatsSection />

      {/* Developer band. Page-owned markup, drawn as a strip of the
          Blueprint skin the developer and MCP pages use, so it reads as a
          door into those pages. It sets the blueprint colors locally; it
          does not use the .skin-blueprint class, which would re-skin the
          whole homepage. */}
      <section className="relative overflow-hidden border-y border-[#2f5ea8] bg-[#0f3d8c] text-[#e9f0ff] [background-image:linear-gradient(#ffffff14_1px,transparent_1px),linear-gradient(90deg,#ffffff14_1px,transparent_1px),linear-gradient(#ffffff08_1px,transparent_1px),linear-gradient(90deg,#ffffff08_1px,transparent_1px)] [background-size:60px_60px,60px_60px,12px_12px,12px_12px] [font-family:var(--font-plex-sans)]">
        <div className="mx-auto max-w-7xl px-6 py-20 md:py-24">
          <div className="grid gap-10 md:grid-cols-12 md:items-center">
            <div className="md:col-span-6">
              <p className="font-mono text-[0.72rem] uppercase tracking-[0.14em] text-[#9fc0ff]">For developers &middot; MCP and REST</p>
              <h2 className="mt-4 [font-family:var(--font-plex-sans)] !font-semibold !tracking-[-0.02em]">
                Bring live roads to your assistant.
              </h2>
              <p className="mt-4 max-w-[46ch] text-lg leading-relaxed text-[#b9cbf3]">
                Ask Claude, ChatGPT, Cursor or any MCP client when to leave, what is
                on the road, and what the weather will be, from the same live feeds
                the map reads.
              </p>
            </div>
            <div className="space-y-5 md:col-span-6 md:pl-6">
              <p className="font-mono text-[0.72rem] uppercase tracking-[0.14em] text-[#9fc0ff]">Connector URL</p>
              <CopyField value={MCP_URL} />
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/mcp#connect"
                  prefetch={false}
                  className="inline-flex h-10 items-center rounded-[3px] bg-[#e9f0ff] px-4 text-sm font-semibold text-[#0f3d8c] transition-colors hover:bg-white"
                >
                  Set up your assistant
                </Link>
                <Link
                  href="/developers"
                  prefetch={false}
                  className="inline-flex h-10 items-center rounded-[3px] border border-dashed border-[#9fc0ff] px-4 text-sm font-semibold text-[#e9f0ff] transition-colors hover:bg-white/10"
                >
                  REST API and keys
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Global footer: rendered once from app/layout.tsx via
          <SiteFooter/>, not repeated here. */}
    </>
  );
}
