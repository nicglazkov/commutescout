import type { Metadata } from "next";
import HeroSection from "@/components/blocks/hero-section-1";
import FeedBench from "@/components/figures/feed-bench";
import {
  DeveloperBand,
  DriveBand,
  FourWays,
  SourceProof,
  SourcesStrip,
} from "@/components/home/sections";

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

// The page argues in one line: one live picture of the road (hero), what
// it reads (strip), four ways to use it, how many feeds become one (the
// feed bench figure, workstream B), proof that every answer names its
// source, the phone app, and the developer surfaces.
export default function Home() {
  return (
    <>
      <HeroSection />
      <SourcesStrip />
      <FourWays />

      <section aria-labelledby="how-title" className="border-t border-cs-line bg-cs-surface-2/50 py-20 md:py-28">
        <div className="cs-container">
          <div className="grid gap-6 md:grid-cols-12">
            <p className="cs-eyebrow md:col-span-3">How it works</p>
            <div className="md:col-span-9">
              <h2 id="how-title" className="cs-h2 max-w-[22ch]">
                Many feeds in, one picture out.
              </h2>
              <p className="cs-lede mt-5 max-w-[40rem]">
                Every record keeps the time its own agency gave it. Duplicates from two feeds
                become one event. A feed that falls behind is flagged, not hidden.
              </p>
            </div>
          </div>
          <div className="mt-12">
            <FeedBench n={1} />
          </div>
        </div>
      </section>

      <SourceProof />
      <DriveBand />
      <DeveloperBand>
        The MCP server&rsquo;s 18 tools and the REST API read the same feeds as the map. Neither
        needs a key; a free key gives your account 2,000 requests a day, shared by all of its keys.
      </DeveloperBand>
    </>
  );
}
