import Link from "next/link";
import { Check } from "lucide-react";
import { AGENCY_FEED_COUNT, STATE_COUNT } from "@/lib/stats";

// Two-tone pricing layout, approved 2026-08-05 from the W01 mockup: a
// navy hero band that continues the site header's surface, with both plan
// cards pulled up to overlap the navy/light seam, and the Pro waitlist
// as a navy panel bled to the card's edges. This replaced the vendored
// Tailark dusk-pricing-1 adaptation; the earlier provenance notes live
// in git history.
//
// Color cohesion with the rest of the site is by construction: every
// surface uses the shared cs-* tokens (the band is the same --cs-navy
// as the header and footer), and the only non-token values are
// white-opacity tints over navy and one color-mix of --cs-sky toward
// white for the waitlist kicker. No new palette entries.
//
// All visible copy is the approved W01 wording. The feed and state
// counts interpolate lib/stats.ts so the drift test keeps them honest.
export default function Pricing() {
  const freeItems = [
    `Live road conditions across ${STATE_COUNT} states`,
    "Route planner with GPX, KML, and print export",
    "Ask about your drive, with a daily cap",
    "3 watch areas: circles up to 25 miles, polygons up to 2,000 square miles, or routes up to 250 miles with a 2 mile buffer",
    `${AGENCY_FEED_COUNT} official agency feeds, including CHP and Caltrans`,
  ];
  const proItems = [
    "More watch areas, and larger ones",
    "Event history and playback for any watch area",
    "Route briefings you can save and export",
    "Pricing has not been set",
  ];

  const checkBadge = (
    <span className="bg-cs-sky/10 text-cs-sky mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full">
      <Check className="size-3" />
    </span>
  );

  return (
    <>
      {/* The navy band. The header above it is the same bg-cs-navy, so
          the two read as one surface; pb leaves room for the cards to
          overlap the seam via negative top margin. */}
      <section className="bg-cs-navy [background-image:radial-gradient(circle_at_18%_0%,var(--cs-navy2)_0%,var(--cs-navy)_55%)] pb-36 max-[420px]:pb-28">
        <div className="mx-auto max-w-[1080px] px-6 pt-14 text-center max-[420px]:pt-10">
          <h1 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-[2.75rem] lg:leading-[1.15]">
            Free today. Pro when it is ready.
          </h1>
          <p className="mx-auto mt-3.5 max-w-[46ch] text-[1.05rem] leading-relaxed text-white/70">
            CommuteScout is free. You get the live map, the route planner, and
            watch areas that tell you what changed before you leave. Pro adds
            more room to watch and a record of what happened.
          </p>
          {/* Road-rule divider: the dashed center-line motif. */}
          <div
            role="presentation"
            className="mx-auto mt-6 h-1 w-[220px] rounded-full [background-image:repeating-linear-gradient(90deg,var(--cs-sky)_0_22px,transparent_22px_34px)]"
          />
        </div>
      </section>

      {/* Plan cards, pulled up into the navy band. */}
      <section className="mx-auto -mt-[104px] grid max-w-[1080px] grid-cols-1 gap-6 px-6 pb-16 max-[420px]:-mt-[76px] lg:grid-cols-2">
        <div className="border-cs-line bg-cs-paper flex flex-col rounded-2xl border p-6 shadow-[0_24px_48px_-12px_rgba(6,16,28,0.45),0_2px_4px_rgba(6,16,28,0.08)] sm:p-8">
          <p className="text-cs-sky text-[0.8rem] font-bold uppercase tracking-[0.08em]">
            Free
          </p>
          <p className="text-cs-ink mt-1.5 flex items-baseline gap-2 text-4xl font-bold tracking-tight">
            $0
            <span className="text-cs-ink/60 text-[0.95rem] font-medium">
              forever
            </span>
          </p>
          <p className="text-cs-ink/60 mt-1 text-[0.92rem]">
            What you need to check the road before you go.
          </p>

          <ul className="text-cs-ink mt-5 flex-1 text-[0.94rem]">
            {freeItems.map((item, index) => (
              <li
                key={index}
                className="border-cs-line flex items-start gap-2.5 border-t py-2.5 leading-normal first:border-t-0"
              >
                {checkBadge}
                {item}
              </li>
            ))}
          </ul>

          <Link
            href="/map"
            prefetch={false}
            className="bg-cs-sky hover:bg-cs-sky/90 mt-6 rounded-[10px] px-5 py-3 text-center text-[0.95rem] font-semibold text-white transition-colors"
          >
            Open the map
          </Link>
        </div>

        <div className="border-cs-sky/60 bg-cs-paper relative flex flex-col overflow-hidden rounded-2xl border p-6 shadow-[0_24px_48px_-12px_rgba(6,16,28,0.45),0_2px_4px_rgba(6,16,28,0.08)] sm:p-8">
          <span className="border-cs-sky/30 bg-cs-sky/10 text-cs-navy2 mb-2.5 inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.72rem] font-bold uppercase tracking-[0.06em] before:size-1.5 before:rounded-full before:bg-cs-sky before:content-['']">
            Coming soon
          </span>
          <p className="text-cs-sky text-[0.8rem] font-bold uppercase tracking-[0.08em]">
            Pro
          </p>
          <p className="text-cs-ink mt-1.5 text-4xl font-bold tracking-tight">
            Not priced yet
          </p>
          <p className="text-cs-ink/60 mt-1 text-[0.92rem]">
            For drivers who watch more ground and want the record to back it
            up.
          </p>

          <ul className="text-cs-ink mt-5 flex-1 text-[0.94rem]">
            {proItems.map((item, index) => (
              <li
                key={index}
                className="border-cs-line flex items-start gap-2.5 border-t py-2.5 leading-normal first:border-t-0"
              >
                {checkBadge}
                {item}
              </li>
            ))}
          </ul>

          {/* The waitlist: a navy panel bled to the card's edges. The
              id anchors the homepage hero's "Get Pro updates" CTA
              (/pricing#waitlist). The form still posts plain to
              /api/waitlist with the honeypot; a no-JS submission lands
              on the endpoint's plain-text response, the accepted v1
              behavior. */}
          <div
            id="waitlist"
            className="bg-cs-navy -mx-6 -mb-6 mt-6 scroll-mt-6 px-6 pb-7 pt-6 text-white sm:-mx-8 sm:-mb-8 sm:px-8"
          >
            <p className="flex items-center gap-2 text-[0.76rem] font-bold uppercase tracking-[0.08em] text-[color-mix(in_srgb,var(--cs-sky)_55%,white)]">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
                className="size-3.5"
              >
                <path
                  d="M12 3a5 5 0 00-5 5v3.2c0 .6-.2 1.2-.6 1.7L5 15.5h14l-1.4-2.6a2.7 2.7 0 01-.6-1.7V8a5 5 0 00-5-5z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <path
                  d="M9.5 18.5a2.5 2.5 0 005 0"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
              Be first to know
            </p>
            <p className="mt-2 text-[1.05rem] font-semibold leading-snug text-white">
              One email, the day Pro opens. Nothing before it.
            </p>

            <form
              method="post"
              action="/api/waitlist"
              className="mt-4 flex flex-wrap gap-2"
            >
              <label htmlFor="waitlist-email" className="sr-only">
                Email address
              </label>
              <input
                id="waitlist-email"
                type="email"
                name="email"
                required
                placeholder="you@example.com"
                className="text-cs-ink placeholder:text-cs-ink/40 focus:outline-cs-sky min-w-0 flex-[1_1_180px] rounded-[10px] border border-white/25 bg-white px-3.5 py-3 text-[0.94rem] focus:outline focus:outline-2 focus:outline-offset-1"
              />
              {/* Honeypot: hidden from sighted users and assistive
                  tech, skipped in tab order. The handler rejects any
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
                className="bg-cs-sky inline-flex shrink-0 items-center gap-1.5 rounded-[10px] px-4.5 py-3 text-[0.94rem] font-semibold text-white transition-colors hover:bg-cs-sky/90"
              >
                Notify me
                <svg
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden="true"
                  className="size-3.5"
                >
                  <path
                    d="M3 10h13M11 5l5 5-5 5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </form>

            <ul className="mt-4 flex flex-col gap-2 border-t border-white/15 pt-4 text-[0.84rem] leading-normal text-white/70">
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 size-3.5 shrink-0 text-[color-mix(in_srgb,var(--cs-sky)_55%,white)]" />
                <span>
                  <strong className="font-semibold text-white">
                    We will send:
                  </strong>{" "}
                  one message, on the day Pro opens.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Check className="mt-0.5 size-3.5 shrink-0 text-[color-mix(in_srgb,var(--cs-sky)_55%,white)]" />
                <span>
                  <strong className="font-semibold text-white">
                    We will not send:
                  </strong>{" "}
                  marketing email, or a price you have not agreed to.
                </span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <p className="text-cs-ink/60 mx-auto max-w-[1080px] px-6 pb-14 text-center text-[0.92rem]">
        Every feed carries its own timestamp, and a stale feed is flagged,
        never hidden.
      </p>
    </>
  );
}
