import type { Metadata } from "next";
import Link from "next/link";

// Privacy page (Task 10 brief): ported into the site shell from the
// pre-reskin src/ca_roads_demo/static/privacy.html. The wording is
// CalOPPA-reviewed and unchanged word-for-word - see the content-
// preservation test in tests/test_site_pages.py and the pre-reskin
// extraction committed at tests/fixtures/privacy_text.txt. Only the
// outer chrome (SiteHeader/SiteFooter, arriving via app/layout.tsx),
// heading levels, and link styling classes were adapted; the old page's
// own topbar nav (which pointed "Live map" at "/", stale now that "/" is
// the marketing homepage) is gone, replaced by the shared SiteHeader.
//
// Owner-approved edit 2026-08-05: the personal name in the Contact
// section's byline was removed, leaving just the email contact.
// tests/fixtures/privacy_text.txt was regenerated from this new content
// with the same _visible() normalization so the content-preservation
// test re-pins on the updated wording.
export const metadata: Metadata = {
  title: "Privacy - CommuteScout",
  description:
    "What CommuteScout collects: nothing identifying you on the map or assistant, just your email and watch areas if you make an account. Nothing is sold.",
  alternates: {
    canonical: "https://commutescout.com/privacy",
  },
  openGraph: {
    title: "Privacy - CommuteScout",
    description:
      "What CommuteScout collects: nothing identifying you on the map or assistant, just your email and watch areas if you make an account. Nothing is sold.",
    url: "https://commutescout.com/privacy",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

export default function PrivacyPage() {
  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-3xl px-6">
        <h1 className="text-cs-ink text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          Privacy
        </h1>
        <p className="text-cs-ink/70 mt-3 text-sm">
          Effective August 18, 2026. Material changes will be posted here with
          a new effective date; account holders get an email when a change
          affects them.
        </p>

        <div className="text-cs-ink/60 mt-8 space-y-8 md:text-lg">
          <p>
            CommuteScout is an independent, one-person project. The short
            version: the map and assistant work without an account and
            store nothing that identifies you; if you create an account for
            watch areas, we store your email and the areas you draw,
            because that is what alerts are; nothing is sold, there are no
            ads, and there is no cross-site tracking.
          </p>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              What we collect
            </h2>
            <ul className="mt-4 list-disc space-y-4 pl-5">
              <li>
                <strong>Without an account</strong> (the map, route
                planner, and assistant): questions you ask the assistant
                are logged to improve answers, tied to a salted daily hash
                instead of your address, with coordinates rounded to about
                a kilometer. If you press the &quot;Was this right?&quot;
                thumbs, that vote is logged with the question the same way
                and reviewed to improve answers. Route and address searches
                are processed to answer them and appear in the same
                anonymized logs. The map opens on your approximate area so
                you do not have to scroll to it: our CDN derives a
                city-level position from your IP address, rounded to about
                a kilometer, and we use it only to choose that first view.
                It is never stored or logged, and no location permission is
                requested. If that lookup is unavailable, your
                browser&apos;s timezone (read locally, never sent to us)
                picks a region instead. No cookies are set and nothing
                about your map activity is kept on your device.
              </li>
              <li>
                <strong>With an account</strong> (watch areas): your email
                address, your sign-in identity from Google or the email
                link you used, the watch areas you draw (names, shapes,
                alert settings), and, if you enable notifications, the push
                subscription for each device. Alert emails we send you are
                delivered through Resend.
              </li>
              <li>
                <strong>If you write to us</strong> (the contact form): the
                name, email address, and message you type. We use them to
                read and answer you, and for nothing else. The message is
                delivered to us as email; we do not add you to any list.
              </li>
              <li>
                <strong>If you join the Pro waitlist</strong>: your email
                address, and nothing else. We use it once, to tell you when
                Pro launches. Ask us at any time to remove it.
              </li>
              <li>
                <strong>Analytics</strong>: cookieless Cloudflare Web
                Analytics counts visits and page timings. It sets no
                cookies, stores no device identifiers, and does not follow
                you to other sites.
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Who touches the data
            </h2>
            <p className="mt-4">
              Categories of third parties that process data to run the
              service. None of them get your data for their own marketing,
              and we do not sell or rent anything:
            </p>
            <ul className="mt-4 list-disc space-y-3 pl-5">
              <li>
                <strong>Google Cloud and Firebase</strong> host the
                service, sign-ins, and the database that stores accounts
                and watch areas.
              </li>
              <li>
                <strong>Anthropic</strong> processes assistant questions to
                generate answers.
              </li>
              <li>
                <strong>Resend</strong> delivers alert and sign-in emails,
                and the messages you send through the contact form.
              </li>
              <li>
                <strong>Cloudflare</strong> provides the cookieless visit
                counts.
              </li>
              <li>
                <strong>TomTom</strong> provides live traffic speeds; the
                server sends it road coordinates being checked, never your
                identity.
              </li>
              <li>
                <strong>State transportation agencies</strong> publish the
                public road data shown for their states (WSDOT, Oregon DOT
                TripCheck, OHGO, UDOT, ADOT, Alaska DOT&PF, CDOT, FDOT, VDOT
                SmarterRoads, Idaho 511, 511NY, WisDOT, INDOT, MnDOT, KDOT,
                NJDOT, MDOT SHA, MDOT MiDrive, MDOT Traffic Mississippi,
                MoDOT, TravelMidwest/IDOT, ALGO Traffic/ALDOT, NCDOT, Iowa
                DOT, KYTC, Oklahoma DOT, HDOT, Louisiana DOTD, DelDOT, TDOT
                SmartWay, the City of Austin, and the NE Compass portal for
                Maine, New Hampshire, and Vermont). Our server fetches
                their public feeds; they never receive anything about you.
                Camera snapshots load in your browser directly from the
                agency&apos;s image host, which sees the request the way
                any image load does.
              </li>
              <li>
                <strong>Stadia Maps</strong> provides map tiles, routing,
                and address lookup; it sees the coordinates and place
                names involved in what you look up, as your browser or
                our server queries it. Map data comes from OpenStreetMap
                contributors.
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Review, change, delete
            </h2>
            <p className="mt-4">
              Signed-in users can see every watch area on the{" "}
              <Link
                href="/watch"
                prefetch={false}
                className="text-cs-sky font-medium hover:underline"
              >
                watch page
              </Link>
              , edit or delete any of them, and delete the whole account
              with the &quot;Delete my account&quot; button there - that
              removes the account record, all watch areas, alert state,
              and push subscriptions immediately. Anything else, or any
              question about data we hold: email{" "}
              <a
                href="mailto:privacy@commutescout.com"
                className="text-cs-sky font-medium hover:underline"
              >
                privacy@commutescout.com
              </a>
              .
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Do Not Track
            </h2>
            <p className="mt-4">
              We do not respond to Do Not Track signals, because there is
              nothing to turn off: no advertising trackers, no cross-site
              tracking, and no cookies on the public site. No other
              parties conduct cross-site tracking through this service.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">
              Where and how long
            </h2>
            <p className="mt-4">
              Data lives in Google Cloud&apos;s us-west1 region.
              Anonymized question logs age out with normal log retention
              (about 30 days). Account data stays until you delete it.
              Push subscriptions are dropped automatically when a device
              unsubscribes. Contact messages stay in our email until we
              have dealt with them. A waitlist email stays until Pro
              launches or until you ask us to remove it, whichever comes
              first. Separately, we keep a long-term archive of the
              public road events themselves (incidents, closures, fires,
              as the agencies publish them) to build history features; it
              contains no user data of any kind.
            </p>
          </div>

          <div>
            <h2 className="text-cs-ink text-xl font-medium">Contact</h2>
            <p className="mt-4">
              <a
                href="mailto:hello@commutescout.com"
                className="text-cs-sky font-medium hover:underline"
              >
                hello@commutescout.com
              </a>{" "}
              (privacy requests:{" "}
              <a
                href="mailto:privacy@commutescout.com"
                className="text-cs-sky font-medium hover:underline"
              >
                privacy@commutescout.com
              </a>
              ). The code behind the service is open source at{" "}
              <a
                href="https://github.com/nicglazkov/commutescout"
                className="text-cs-sky font-medium hover:underline"
              >
                github.com/nicglazkov/commutescout
              </a>
              , so you can check any of this yourself.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
