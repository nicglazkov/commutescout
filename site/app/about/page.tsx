import type { Metadata } from "next";

// About page takes its own metadata (Task 9 brief). Title/description
// shape follows the pricing page's metadata export (Task 8); description is
// one sentence, Google style.
export const metadata: Metadata = {
  title: "About - CommuteScout",
  description:
    "CommuteScout reads official agency feeds instead of scraping, and stamps every response with per-source timestamps.",
  alternates: {
    canonical: "https://commutescout.com/about",
  },
  openGraph: {
    title: "About - CommuteScout",
    description:
      "CommuteScout reads official agency feeds instead of scraping, and stamps every response with per-source timestamps.",
    url: "https://commutescout.com/about",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

export default function AboutPage() {
  return (
    // Plain page-owned content section: none of the six vendored Dusk block
    // types (hero, feature grid, stat band, pricing, FAQ, footer) fit a
    // short prose page, so this composes directly rather than forcing one.
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-3xl px-6">
        <h1 className="text-cs-ink text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          About
        </h1>

        {/* Copy sources (Task 9 brief): the first two paragraphs are the
            README's opening two sentences verbatim (already sentence case);
            the data story sentence is the brief's exact copy; the third
            paragraph is the README's "License & sustainability" section,
            substance kept verbatim. */}
        <div className="text-cs-ink/60 mt-8 space-y-6 text-balance md:text-lg">
          <p>
            CommuteScout reads 53 official agency feeds (CHP dispatch, state
            DOT closures and incidents, chain controls, cameras, message
            signs, wildfire perimeters, road weather, toll prices) and turns
            them into one live picture of the road. Look at the map, plan a
            route and see what is actually on it, or ask about a drive in
            plain English.
          </p>

          <p>
            Every layer comes from official agency feeds. CommuteScout never
            scrapes, and every response carries per-source timestamps.
          </p>

          <p>
            CommuteScout is{" "}
            <a
              href="https://github.com/nicglazkov/commutescout/blob/main/LICENSE"
              className="text-cs-sky font-medium hover:underline"
            >
              MIT licensed
            </a>
            : the map, the planner, the MCP server, and every data parser,
            with no open-core carve-outs. The hosted app at commutescout.com
            will soon offer optional premium features (deeper history, more
            alerts); that is what funds the servers and keeps the free tier
            free.
          </p>
        </div>

        <a
          href="https://github.com/nicglazkov/commutescout"
          className="text-cs-sky mt-8 inline-block font-medium hover:underline"
        >
          View the code on GitHub
        </a>
      </div>
    </section>
  );
}
