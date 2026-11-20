import type { Metadata } from "next";
import HeroSection from "@/components/blocks/hero-section-1";
import { Coverage, DeveloperBand, DriveBand, FourWays } from "@/components/home/sections";

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
    "CommuteScout tracks live road conditions from 53 official sources across 37 states and plans routes that avoid closures and chain controls.",
  alternates: {
    canonical: "https://commutescout.com/",
  },
  openGraph: {
    title: "CommuteScout: live road conditions, traffic map, and route planner",
    description:
      "CommuteScout tracks live road conditions from 53 official sources across 37 states and plans routes that avoid closures and chain controls.",
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

// The page in order: the live map (hero, with a real screenshot), what
// you can do with it, what each state gets, the phone app as a compact
// band, and the developer surfaces.
export default function Home() {
  return (
    <>
      <HeroSection />
      <FourWays />
      <Coverage />
      <DriveBand />
      <DeveloperBand>
        The MCP server&rsquo;s 18 tools and the REST API read the same sources as the map. Both take
        a free API key, which gives your account 2,000 requests a day, shared by all of its keys.
      </DeveloperBand>
    </>
  );
}
