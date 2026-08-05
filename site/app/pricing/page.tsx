import type { Metadata } from "next";
import Pricing from "@/components/blocks/pricing-1";

// Pricing page takes its own metadata (Task 8 brief). Title/description
// shape follows the homepage's metadata export (Task 7); description is
// one sentence, Google style.
export const metadata: Metadata = {
  title: "Pricing - CommuteScout",
  description:
    "See what's included in CommuteScout's free plan and join the waitlist for Pro: bigger watch areas, event history, and route briefings.",
  alternates: {
    canonical: "https://commutescout.com/pricing",
  },
  openGraph: {
    title: "Pricing - CommuteScout",
    description:
      "See what's included in CommuteScout's free plan and join the waitlist for Pro: bigger watch areas, event history, and route briefings.",
    url: "https://commutescout.com/pricing",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

export default function PricingPage() {
  return (
    <>
      <Pricing />

      {/* Pro waitlist. Page-owned markup, like the homepage's developer
          band (Task 7): not one of the six required vendored block types,
          so it isn't a components/blocks file. The section id is the
          scroll target the homepage hero's "Get Pro updates" CTA links to
          (/pricing#waitlist). Plain form POST to /api/waitlist (Task 12):
          no JS submission handler, matching the brief's exact markup. The
          endpoint returns a plain-text response rather than a redirect, so
          a no-JS submission lands on a plain "You're on the list." page;
          that is the accepted v1 behavior.
          Visual-engagement pass (polish phase 3): only the surrounding
          band/card wrapper and heading style changed here, framing the
          form to match the navy-plinth cards above it - the <form>
          element itself, its fields/attributes/honeypot/action, and the
          explainer sentence below it are untouched byte-for-byte. */}
      <section id="waitlist" className="scroll-mt-6 pb-16 md:pb-20">
        <div className="mx-auto max-w-7xl px-6">
          <div className="border-cs-line bg-cs-paper max-w-xl rounded-2xl border p-6 sm:p-8">
            <h2 className="text-cs-ink text-2xl font-medium tracking-tight">
              Get Pro updates
            </h2>

            <form
              method="post"
              action="/api/waitlist"
              className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center"
            >
              <input
                type="email"
                name="email"
                required
                placeholder="you@example.com"
                className="border-cs-line bg-cs-paper text-cs-ink placeholder:text-cs-ink/40 focus:ring-cs-sky w-full rounded-lg border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 sm:max-w-xs"
              />
              {/* Honeypot: hidden from sighted users and assistive tech,
                  skipped in tab order. Task 12's handler rejects any
                  submission that fills this field. */}
              <input
                type="text"
                name="website"
                tabIndex={-1}
                autoComplete="off"
                className="hidden"
                aria-hidden="true"
              />
              <button
                type="submit"
                className="bg-cs-sky hover:bg-cs-sky/90 shrink-0 rounded-full px-5 py-2.5 text-sm font-medium text-white transition-colors"
              >
                Notify me when Pro launches
              </button>
            </form>

            <p className="text-cs-ink/60 mt-4 text-sm">
              Leave your email and we&apos;ll tell you when Pro launches. Nothing
              else, no newsletter.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
