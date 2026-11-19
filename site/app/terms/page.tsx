import type { Metadata } from "next";

// Terms page (Task 10 brief): ported into the site shell from the
// pre-reskin src/ca_roads_demo/static/terms.html. The wording is
// CalOPPA-reviewed and unchanged word-for-word - see the content-
// preservation test in tests/test_site_pages.py and the pre-reskin
// extraction committed at tests/fixtures/terms_text.txt. Only the outer
// chrome (SiteHeader/SiteFooter, arriving via app/layout.tsx), heading
// levels, and link styling classes were adapted; the old page's own
// topbar nav (which pointed "Live map" at "/", stale now that "/" is the
// marketing homepage) is gone, replaced by the shared SiteHeader.
//
// Owner-approved edit 2026-11-19: the blanket "don't use the service
// while driving" line contradicted the CommuteScout Drive navigation
// apps; it is replaced by a driving-safety clause, and the page now
// covers the apps, API keys, account-level limits and plugins. The
// fixture was regenerated from the build.
export const metadata: Metadata = {
  title: "Terms - CommuteScout",
  description:
    "Plain-language terms for using CommuteScout: informational only, not a substitute for your official DOT source, and provided as is with no warranty.",
  alternates: {
    canonical: "https://commutescout.com/terms",
  },
  openGraph: {
    title: "Terms - CommuteScout",
    description:
      "Plain-language terms for using CommuteScout: informational only, not a substitute for your official DOT source, and provided as is with no warranty.",
    url: "https://commutescout.com/terms",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

export default function TermsPage() {
  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-3xl px-6">
        <h1 className="text-cs-ink text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          Terms of use
        </h1>
        <p className="text-cs-ink/70 mt-3 text-sm">
          Effective November 19, 2026.
        </p>

        <div className="text-cs-ink/60 mt-8 space-y-8 md:text-lg">
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-5 py-4 font-medium text-amber-900">
            CommuteScout is informational only. Data can be delayed,
            incomplete, or wrong. Always verify with your state&apos;s
            official 511 service or DOT map (for California,{" "}
            <a
              href="https://quickmap.dot.ca.gov"
              className="text-cs-sky hover:underline"
            >
              quickmap.dot.ca.gov
            </a>
            ) before you drive, and never rely on this service for
            evacuation or any emergency decision. If you are in danger,
            call 911.
          </p>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              What this is
            </h2>
            <p className="mt-4">
              A free, independent project that displays public road data
              from state and federal sources across the country - CHP,
              Caltrans, other state transportation agencies, and national
              wildfire and weather feeds - plus routing, an AI assistant,
              watch-area alerts, the CommuteScout Drive navigation apps for
              iPhone and Android, and an MCP server and REST API. Coverage
              varies by state and the map says so
              where it is missing. It is not affiliated with, endorsed by,
              or operated by any government agency. Names of data sources
              are used to describe where data comes from, nothing more.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">Using it</h2>
            <ul className="mt-4 list-disc space-y-3 pl-5">
              <li>
                Drive safely. Set your route before you start, and
                don&apos;t look at or touch the screen while the vehicle is
                moving; let the Drive app&apos;s voice guidance and alerts do
                the talking, or have a passenger handle it. Obey traffic
                laws, road signs, and officials on the scene: they win over
                anything the app or map says, including a route that tells
                you to turn where you shouldn&apos;t.
              </li>
              <li>
                Routes, drive times, and alerts are estimates built from
                public feeds and can be wrong or out of date. They are not a
                substitute for your state&apos;s official 511 or DOT
                information.
              </li>
              <li>
                Don&apos;t abuse it: no scraping at volumes that degrade it
                for others, no attempts to bypass rate limits or access
                controls, no using the assistant for anything other than
                road questions.
              </li>
              <li>
                API keys belong to your account. Keep them secret, and
                don&apos;t put one in a web page or app that others can
                read. Request limits apply per account, shared by all of
                its keys, and per address without a key; we can change
                limits and revoke keys that are abused.
              </li>
              <li>
                Plugins can be run by people other than us. What a
                plugin shows is its operator&apos;s, not ours, and reports
                you post go to the plugins you have switched on as the{" "}
                <a
                  href="/privacy"
                  className="text-cs-sky font-medium hover:underline"
                >
                  privacy policy
                </a>{" "}
                describes.
              </li>
              <li>
                Watch-area accounts are an invite-gated trial. We can
                approve, limit, or revoke access at any time. Areas are
                checked about every five minutes, and alert delivery is best
                effort - alerts can be late, missed, or wrong.
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Ending access
            </h2>
            <p className="mt-4">
              We can suspend or end access for anyone who violates these
              terms or abuses the service, with or without notice. You can
              stop using the service whenever you like.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              No warranty, limited liability
            </h2>
            <p className="mt-4">
              The service is provided as is, without warranties of any
              kind, express or implied, including fitness for a
              particular purpose. To the maximum extent permitted by law,
              the operator is not liable for any damages arising from use
              of the service or reliance on its data, including decisions
              made based on alerts, maps, routes, or assistant answers.
              That limit covers indirect, incidental, consequential,
              special, and punitive damages alike, along with any lost
              data, profits, or time, even if we were warned they were
              possible. Road conditions are verified by official sources,
              not by us; your driving decisions are yours.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">The code</h2>
            <p className="mt-4">
              The software is open source under the MIT license at{" "}
              <a
                href="https://github.com/nicglazkov/commutescout"
                className="text-cs-sky font-medium hover:underline"
              >
                github.com/nicglazkov/commutescout
              </a>
              . These terms cover this hosted instance, not the code - you
              are welcome to run your own.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Copyright and takedowns
            </h2>
            <p className="mt-4">
              Almost everything shown here comes from public agency feeds,
              but if you believe something on the service infringes your
              copyright, email{" "}
              <a
                href="mailto:hello@commutescout.com"
                className="text-cs-sky font-medium hover:underline"
              >
                hello@commutescout.com
              </a>{" "}
              with a description of the work, where it appears, and how to
              reach you. We&apos;ll review it and remove anything that
              shouldn&apos;t be here.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Changes to these terms
            </h2>
            <p className="mt-4">
              We may update these terms from time to time. We&apos;ll post
              the new version here with a new effective date, and for
              significant changes we&apos;ll email account holders.
              Continuing to use the service after a change means you accept
              the updated terms.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">General</h2>
            <p className="mt-4">
              If any part of these terms is found unenforceable, the rest
              still applies. Together with our{" "}
              <a
                href="/privacy"
                className="text-cs-sky font-medium hover:underline"
              >
                privacy policy
              </a>
              , these terms are the whole agreement between you and the
              operator about the service.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Governing law and contact
            </h2>
            <p className="mt-4">
              These terms are governed by California law. Questions:{" "}
              <a
                href="mailto:hello@commutescout.com"
                className="text-cs-sky font-medium hover:underline"
              >
                hello@commutescout.com
              </a>
              .
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
