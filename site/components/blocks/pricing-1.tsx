import Link from "next/link";
import { ArrowRight, Check, Mail } from "lucide-react";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";
import { FormNotice } from "@/components/form-notice";

// /pricing. Two plans side by side on one hairline grid: Free, which is
// everything the site does today, and Pro, which is coming soon. Pro has
// no price on purpose. The slot says "Coming soon" and names the address
// to write to. The Pro waitlist form (POST /api/waitlist, honeypot
// "website", anchor #waitlist) lives in the Pro column.
//
// The feed and state counts interpolate lib/stats.ts so the drift test in
// tests/test_snapshot.py keeps them honest. Limits match the code: keyed
// API limits are per account and shared by all of its keys.
const PRO_EMAIL = "hello@commutescout.com";

const freeItems = [
  `The live map: ${AGENCY_FEED_COUNT} official sources across ${STATE_COUNT} states`,
  "Route planner with GPX, KML and print export",
  "Ask about your drive, with a daily cap",
  "3 watch areas (accounts need approval for now): circles up to 25 miles, polygons up to 2,000 square miles, or routes up to 250 miles with a 2 mile buffer",
  "CommuteScout Drive for iPhone and Android, free while in beta",
];
const proItems = [
  "More watch areas, and larger ones",
  "Event history and playback for any watch area",
  "Route briefings you can save and export",
  "A higher daily API limit",
];

// The developer limits, in their own section under the plans. Keyed
// limits are per account and shared by all of its keys
// (src/ca_roads_mcp/ratelimit.py); the hosted service requires a key.
const apiRows = [
  { plan: "Free", value: "2,000", note: "requests a day per account" },
  { plan: "Pro", value: "10,000", note: "requests a day per account" },
];

function Item({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-3 border-t border-cs-line py-3 text-[0.9375rem] leading-relaxed text-cs-ink-2 first:border-t-0">
      <Check aria-hidden className="mt-1 size-4 shrink-0 text-cs-ok" strokeWidth={2.25} />
      <span>{children}</span>
    </li>
  );
}

export default function Pricing() {
  return (
    <>
      <section className="cs-container pb-10 pt-14 md:pb-14 md:pt-20">
        <h1 className="cs-display cs-rise">Pricing</h1>
      </section>

      <section aria-label="Plans" className="cs-container pb-16 md:pb-20">
        <div className="grid overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface shadow-[var(--cs-shadow-sm)] lg:grid-cols-2">
          {/* Free */}
          <div className="flex flex-col p-6 sm:p-8 lg:p-10">
            <div className="flex items-center justify-between gap-4">
              <h2 className="cs-h3">Free</h2>
              <span className="cs-data rounded-full bg-cs-ok-soft px-2.5 py-1 text-xs text-cs-ok">
                Available now
              </span>
            </div>
            <p className="mt-6 flex items-baseline gap-2">
              <span className="cs-data text-[2.75rem] font-medium leading-none tracking-[-0.04em] text-cs-ink">
                $0
              </span>
              <span className="text-[0.9375rem] text-cs-ink-3">no card, no trial</span>
            </p>
            <p className="mt-3 text-[0.9375rem] text-cs-ink-2">
              What you need to check the road before you go.
            </p>
            <Link
              href="/map"
              prefetch={false}
              className="mt-7 inline-flex h-11 items-center justify-center rounded-[var(--cs-radius-md)] bg-cs-accent px-5 text-[0.9375rem] font-medium text-cs-accent-ink shadow-[var(--cs-shadow-sm)] transition-colors duration-150 hover:bg-cs-accent-hover"
            >
              Open the map
            </Link>
            <p className="mt-9 text-sm font-medium text-cs-ink">Included</p>
            <ul className="mt-2 flex-1">
              {freeItems.map((t) => (
                <Item key={t}>{t}</Item>
              ))}
            </ul>
          </div>

          {/* Pro */}
          <div className="flex flex-col border-t border-cs-line bg-cs-surface-2/60 p-6 sm:p-8 lg:border-l lg:border-t-0 lg:p-10">
            <div className="flex items-center justify-between gap-4">
              <h2 className="cs-h3">Pro</h2>
              <span className="cs-data rounded-full bg-cs-accent-soft px-2.5 py-1 text-xs text-cs-accent">
                Waitlist open
              </span>
            </div>
            <p className="mt-6 text-[2.75rem] font-semibold leading-none tracking-[-0.035em] text-cs-ink">
              Coming soon
            </p>
            <p className="mt-3 text-[0.9375rem] text-cs-ink-2">
              More room to watch, and a record of what happened. Questions? Write to us.
            </p>
            <a
              href={`mailto:${PRO_EMAIL}?subject=CommuteScout%20Pro`}
              className="mt-7 inline-flex h-11 items-center justify-center gap-2 rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface px-5 text-[0.9375rem] font-medium text-cs-ink transition-colors duration-150 hover:bg-cs-bg"
            >
              <Mail aria-hidden className="size-4" />
              Email {PRO_EMAIL}
            </a>
            <p className="mt-9 text-sm font-medium text-cs-ink">Everything in Free, plus</p>
            <ul className="mt-2">
              {proItems.map((t) => (
                <Item key={t}>{t}</Item>
              ))}
            </ul>

            {/* The waitlist. A no-JS post lands back here with ?notice=. */}
            <div id="waitlist" className="mt-auto scroll-mt-24 pt-8">
              <div className="rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-surface p-5">
                <h3 className="text-[0.9375rem] font-semibold text-cs-ink">Get one email when Pro opens</h3>
                <p className="mt-1 text-sm text-cs-ink-3">
                  One message, the day it opens. No marketing email.
                </p>
                <form method="post" action="/api/waitlist" className="mt-4 flex flex-wrap gap-2">
                  <label htmlFor="waitlist-email" className="sr-only">
                    Email address
                  </label>
                  <input
                    id="waitlist-email"
                    type="email"
                    name="email"
                    required
                    autoComplete="email"
                    placeholder="you@example.com"
                    className="h-11 min-w-0 flex-[1_1_12rem] rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-bg px-3.5 text-[0.9375rem] text-cs-ink placeholder:text-cs-ink-3"
                  />
                  {/* Honeypot: hidden, skipped in tab order; the handler
                      rejects any post that fills it. */}
                  <input type="text" name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />
                  <button
                    type="submit"
                    className="inline-flex h-11 shrink-0 items-center rounded-[var(--cs-radius-md)] bg-cs-ink px-4 text-[0.9375rem] font-medium text-cs-bg transition-opacity duration-150 hover:opacity-90"
                  >
                    Notify me
                  </button>
                </form>
                <FormNotice
                  messages={{
                    joined: { ok: true, text: "You're on the list. One email, the day Pro opens." },
                    invalid: { ok: false, text: "Enter a valid email address." },
                    unavailable: { ok: false, text: "Signups are unavailable right now. Try again later." },
                  }}
                />
              </div>
            </div>
          </div>
        </div>

      </section>

      {/* The API and MCP server: their own section, so the plan cards
          stay about the product and developers find the limits in one place. */}
      <section aria-labelledby="api-title" className="border-t border-cs-line bg-cs-surface py-16 md:py-20">
        <div className="cs-container grid gap-10 lg:grid-cols-12 lg:items-center lg:gap-10">
          <div className="lg:col-span-5">
            <p className="cs-eyebrow">For developers</p>
            <h2 id="api-title" className="cs-h2 mt-3">
              API and MCP server
            </h2>
            <p className="mt-4 max-w-[30rem] text-[0.9375rem] leading-relaxed text-cs-ink-2">
              Both take a free API key. The daily limit belongs to your account and is shared by
              all of its keys.
            </p>
            <Link href="/developers" prefetch={false} className="cs-link mt-5 inline-flex min-h-6 items-center gap-1 text-[0.9375rem]">
              Keys and every limit in the developer docs
              <ArrowRight aria-hidden className="size-3.5" />
            </Link>
          </div>
          <dl className="grid overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-bg sm:grid-cols-2 lg:col-span-7">
            {apiRows.map((r, i) => (
              <div key={r.plan} className={`p-6 sm:p-7 ${i > 0 ? "border-t border-cs-line sm:border-l sm:border-t-0" : ""}`}>
                <dt className="text-sm font-medium text-cs-ink-2">{r.plan}</dt>
                <dd className="mt-3 flex flex-col gap-2">
                  <span className="cs-data text-[2.25rem] font-medium leading-none tracking-[-0.04em] text-cs-ink">{r.value}</span>
                  <span className="text-sm text-cs-ink-3">{r.note}</span>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </>
  );
}
