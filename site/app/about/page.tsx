import type { Metadata } from "next";
import Link from "next/link";
import UsCoverageMap from "@/components/figures/us-coverage-map";
import { STATE_COUNT } from "@/lib/stats";

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

const principles = [
  {
    title: "Official feeds only.",
    body: "Every layer comes from an agency that publishes it: state DOTs, highway patrols, the National Weather Service and national wildfire feeds. CommuteScout never scrapes.",
  },
  {
    title: "Every answer shows its source.",
    body: "Each response lists the feeds it read, whether each one answered, and when that feed itself last changed, not when we fetched it.",
  },
  {
    title: "Stale is flagged, never hidden.",
    body: "A feed past its stale limit still shows, marked as stale, so you can judge it yourself. A feed that is down is named, and the others still answer.",
  },
  {
    title: "Open source, all of it.",
    body: "The map, the planner, the MCP server and every data parser are MIT licensed, with no open-core carve-outs.",
  },
];

export default function AboutPage() {
  return (
    <>
      <section className="cs-container pb-16 pt-14 md:pb-24 md:pt-20">
        <div className="grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <p className="cs-eyebrow cs-rise">About</p>
            <h1 className="cs-display cs-rise mt-5 [animation-delay:60ms]">
              One live picture of the road, read from the agencies that run it.
            </h1>
          </div>
          <div className="cs-rise space-y-5 text-[1.0625rem] leading-relaxed text-cs-ink-2 [animation-delay:120ms] lg:col-span-5 lg:pt-12">
            <p>
              CommuteScout reads 53 official agency feeds (highway patrol dispatch, state DOT
              closures and incidents, chain controls, cameras, message signs, wildfire perimeters,
              road weather, toll prices) and turns them into one live picture of the road.
            </p>
            <p>
              Look at the map, plan a route and see what is actually on it, or ask about a drive in
              plain English.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="coverage-title" className="border-t border-cs-line bg-cs-surface py-20 md:py-28">
        <div className="cs-container">
          <div className="grid gap-6 md:grid-cols-12">
            <p className="cs-eyebrow md:col-span-3">Coverage</p>
            <div className="md:col-span-9">
              <h2 id="coverage-title" className="cs-h2">
                {STATE_COUNT} states with their own feeds, and the nationwide layers everywhere.
              </h2>
              <p className="cs-lede mt-4 max-w-[42rem]">
                Depth depends on what each state publishes. Wildfires, weather alerts and the
                traffic overlay cover every state.
              </p>
            </div>
          </div>
          <div className="mt-12">
            <UsCoverageMap n={1} />
          </div>
        </div>
      </section>

      <section aria-labelledby="principles-title" className="border-t border-cs-line py-20 md:py-28">
        <div className="cs-container grid gap-10 md:grid-cols-12">
          <div className="md:col-span-4">
            <p className="cs-eyebrow">How it works</p>
            <h2 id="principles-title" className="cs-h2 mt-4 md:sticky md:top-28">
              Four rules the data follows.
            </h2>
          </div>
          <ol className="md:col-span-8">
            {principles.map((p, i) => (
              <li key={p.title} className="grid gap-2 border-t border-cs-line py-7 first:border-t-0 first:pt-0 sm:grid-cols-[3.5rem_1fr]">
                <span className="cs-data text-sm text-cs-ink-3">0{i + 1}</span>
                <div>
                  <h3 className="cs-h3">{p.title}</h3>
                  <p className="mt-2 max-w-[56ch] text-[0.9375rem] leading-relaxed text-cs-ink-2">{p.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="funding-title" className="border-t border-cs-line bg-cs-surface py-20 md:py-24">
        <div className="cs-container grid gap-8 md:grid-cols-12 md:items-end">
          <div className="md:col-span-7">
            <p className="cs-eyebrow">License and sustainability</p>
            <h2 id="funding-title" className="cs-h2 mt-4">Free to use, free to read.</h2>
            <p className="cs-lede mt-4 max-w-[40rem]">
              CommuteScout is{" "}
              <a href="https://github.com/nicglazkov/commutescout/blob/main/LICENSE" className="cs-link">
                MIT licensed
              </a>
              . The hosted app will offer optional Pro features (more watch areas, event history);
              that is what funds the servers and keeps the free tier free.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 md:col-span-5 md:justify-end">
            <a
              href="https://github.com/nicglazkov/commutescout"
              className="inline-flex h-11 items-center rounded-[var(--cs-radius-md)] bg-cs-ink px-5 text-[0.9375rem] font-medium text-cs-bg transition-opacity hover:opacity-90"
            >
              View the code on GitHub
            </a>
            <Link
              href="/contact"
              prefetch={false}
              className="inline-flex h-11 items-center rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface px-5 text-[0.9375rem] font-medium text-cs-ink transition-colors hover:bg-cs-surface-2"
            >
              Contact
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
