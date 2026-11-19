import type { Metadata } from "next";
import Link from "next/link";
import UsCoverageMap from "@/components/figures/us-coverage-map";

// About page takes its own metadata (Task 9 brief). Title/description
// shape follows the pricing page's metadata export (Task 8); description is
// one sentence, Google style.
export const metadata: Metadata = {
  title: "About - CommuteScout",
  description:
    "CommuteScout puts official road data from state agencies, the National Weather Service and wildfire agencies on one live map, with the source and time on every answer.",
  alternates: {
    canonical: "https://commutescout.com/about",
  },
  openGraph: {
    title: "About - CommuteScout",
    description:
      "CommuteScout puts official road data from state agencies, the National Weather Service and wildfire agencies on one live map, with the source and time on every answer.",
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
    title: "Only official sources.",
    body: "Every layer comes from the agency that publishes it, such as a state transportation department, a highway patrol or the National Weather Service. Nothing is scraped.",
  },
  {
    title: "Every answer names its sources.",
    body: "You can see where each answer came from, and when each source last updated.",
  },
  {
    title: "Old data is labeled.",
    body: "If a source has not updated in a while, its data still shows, marked as out of date. If a source is down, CommuteScout says which one.",
  },
];

export default function AboutPage() {
  return (
    <>
      <section className="cs-container pb-16 pt-14 md:pb-24 md:pt-20">
        <div className="grid gap-8 lg:grid-cols-12 lg:items-end lg:gap-10">
          <h1 className="cs-display cs-rise lg:col-span-6">Official road data.</h1>
          <p className="cs-lede cs-rise max-w-[34rem] [animation-delay:120ms] lg:col-span-6">
            CommuteScout puts 53 official sources on one live map: state transportation
            departments, highway patrols, the National Weather Service and wildfire agencies.
          </p>
        </div>
      </section>

      <section aria-labelledby="coverage-title" className="border-t border-cs-line bg-cs-surface py-20 md:py-28">
        <div className="cs-container">
          <h2 id="coverage-title" className="cs-h2">
            Coverage
          </h2>
          <p className="cs-lede mt-4 max-w-[40rem]">
            Weather alerts, wildfires and live traffic cover every state. The stronger a
            state&rsquo;s blue, the more road data comes from its own agencies.
          </p>
          <div className="mt-12">
            <UsCoverageMap n={1} />
          </div>
        </div>
      </section>

      <section aria-labelledby="principles-title" className="border-t border-cs-line py-20 md:py-28">
        <div className="cs-container grid gap-10 md:grid-cols-12">
          <h2 id="principles-title" className="cs-h2 md:col-span-4">
            What you can count on
          </h2>
          <ul className="md:col-span-8">
            {principles.map((p) => (
              <li key={p.title} className="border-t border-cs-line py-7 first:border-t-0 first:pt-0">
                <h3 className="cs-h3">{p.title}</h3>
                <p className="mt-2 max-w-[56ch] text-[0.9375rem] leading-relaxed text-cs-ink-2">{p.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section aria-labelledby="source-title" className="border-t border-cs-line bg-cs-surface py-20 md:py-24">
        <div className="cs-container grid gap-8 md:grid-cols-12 md:items-end">
          <div className="md:col-span-7">
            <h2 id="source-title" className="cs-h2">Open source</h2>
            <p className="cs-lede mt-4 max-w-[40rem]">
              The site, the MCP server and the apps are{" "}
              <a href="https://github.com/nicglazkov/commutescout/blob/main/LICENSE" className="cs-link">
                MIT licensed
              </a>
              . The map is free. A Pro plan is coming.
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
