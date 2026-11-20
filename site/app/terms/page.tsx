import type { Metadata } from "next";

import { LegalPage, legalStyles as s } from "./_legal/legal-page";

// Terms of use. Facts here (limits, alert behavior, what the apps do) were
// checked against the code on 2026-11-19; the evidence table and the
// legal-requirements checklist are in the rebuild report (realsite/C.md).
// The rewrite is not legal advice and lists open owner/lawyer decisions
// there.
//
// The wording is pinned by the content-preservation test in
// tests/test_site_pages.py against tests/fixtures/terms_text.txt, which
// was regenerated from this build on 2026-11-19 with the test's own
// _visible() normalization. Regenerate it after any approved wording change.
export const metadata: Metadata = {
  title: "Terms - CommuteScout",
  description:
    "The terms for using CommuteScout, its apps and its API: information only, drive safely, verify with your official 511 or DOT source, provided as is.",
  alternates: {
    canonical: "https://commutescout.com/terms",
  },
  openGraph: {
    title: "Terms - CommuteScout",
    description:
      "The terms for using CommuteScout, its apps and its API: information only, drive safely, verify with your official 511 or DOT source, provided as is.",
    url: "https://commutescout.com/terms",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

const HELLO = "hello@commutescout.com";

function Mail({ to }: { to: string }) {
  return <a href={`mailto:${to}`}>{to}</a>;
}

const summary = [
  <>
    <strong>Information only.</strong> Road data can be late, incomplete or
    wrong. Check your state&rsquo;s official 511 or DOT source before you go.
  </>,
  <>
    <strong>Drive safely.</strong> Set your route before you move, keep your
    hands off the screen, and obey the law, signs and officials on the scene.
  </>,
  <>
    <strong>It is free and provided as is.</strong> No warranty, and our
    liability is limited as far as the law allows.
  </>,
  <>
    <strong>Play fair.</strong> No abuse, no getting around limits, no false
    reports. API keys belong to your account; keep them secret.
  </>,
  <>
    <strong>Plugins and data belong to others.</strong> Plugins can be run by
    other people, and the road data comes from public agencies.
  </>,
  <>
    <strong>California law applies.</strong> Questions or disputes: start with{" "}
    <Mail to={HELLO} />.
  </>,
];

export default function TermsPage() {
  return (
    <LegalPage
      eyebrow="Legal"
      title="Terms of use"
      effective="November 19, 2026"
      updated="Covers commutescout.com, the MCP server and API, and the CommuteScout Drive apps."
      lede={
        <>
          These terms are an agreement between you and CommuteScout
          (&ldquo;CommuteScout&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;). By using the
          website, the live map, the assistant, watch-area alerts, the MCP
          server, the REST API or the CommuteScout Drive apps (together,
          &ldquo;the service&rdquo;), you agree to them. If you do not agree,
          please do not use the service.
        </>
      }
      summaryTitle="The short version"
      summaryNote="A summary for convenience. The numbered sections below are the terms."
      summary={summary}
      summaryKeys={[3]}
      sections={[
        {
          id: "service",
          title: "What CommuteScout is",
          body: (
            <>
              <p>
                CommuteScout is a free, independent project. It shows public
                road data from state, local and federal sources (incidents,
                closures, chain controls, wildfires, cameras, signs and
                weather), adds routing, traffic, an AI assistant, watch-area
                alerts and community road reports, and offers the CommuteScout
                Drive navigation apps for iPhone and Android, an MCP server and
                a REST API. Coverage differs from state to state, and the map
                says where data is missing.
              </p>
              <p>
                CommuteScout is not affiliated with, endorsed by or operated by
                any government agency. Agency names are used only to say where
                data comes from. Parts of the service are early releases (for
                example, the iPhone app is a TestFlight beta and watch areas are
                an invite-only trial) and may change, break or stop.
              </p>
              <p>
                The service is free. A paid Pro plan is coming soon; if we
                offer one, its price and terms will be shown to you before you
                pay anything.
              </p>
            </>
          ),
        },
        {
          id: "safety",
          title: "Driving safety",
          body: (
            <>
              <div className={`${s.callout} ${s.calloutWarn}`} role="note">
                <span className={s.calloutTitle}>
                  Your eyes belong on the road.
                </span>
                Never let CommuteScout distract you from driving. If you are in
                danger, call 911.
              </div>
              <ul>
                <li>
                  Set your route and settings before you start moving. Do not
                  look at, type on or touch the screen while the vehicle is
                  moving: rely on spoken directions and alerts, have a
                  passenger handle the app, or pull over somewhere safe first.
                  This includes posting road reports and asking the assistant.
                </li>
                <li>
                  Use a phone mount where the law requires one, and follow your
                  state&rsquo;s laws on phone use while driving.
                </li>
                <li>
                  Obey traffic laws, road signs, signals, closures and
                  directions from police, fire and road crews. They always win
                  over anything the service says, including a route that tells
                  you to turn where you should not.
                </li>
                <li>
                  Use your own judgment about every route. A suggested route can
                  be closed, unsafe, seasonal, unpaved, flooded, or unsuitable
                  for your vehicle. The service is not designed for trucks,
                  oversize or hazardous loads, or emergency vehicles.
                </li>
                <li>
                  Never rely on the service for evacuation, wildfire, flood or
                  any other emergency decision. Follow official emergency
                  instructions.
                </li>
              </ul>
            </>
          ),
        },
        {
          id: "information",
          title: "Information only: data, sources and accuracy",
          body: (
            <>
              <p>
                Road conditions, routes, drive times, speed limits, traffic,
                weather, camera images, alerts and assistant answers are
                estimates built from public feeds, third-party services and
                other users. They can be delayed, incomplete, out of date or
                wrong, and feeds can stop without warning. They are not a
                substitute for your state&rsquo;s official 511 service or
                transportation department, which you should check before you
                travel.
              </p>
              <p>
                The data belongs to its sources. Agency data is published by
                the agencies listed on{" "}
                <a href="/data-sources">Data sources</a>. Map data is &copy;
                OpenStreetMap contributors. Routing and address search are by
                Stadia Maps, live traffic speeds by TomTom, and weather by the
                National Weather Service. Their own terms and licenses apply to
                their data.
              </p>
            </>
          ),
        },
        {
          id: "account",
          title: "Your account",
          body: (
            <>
              <p>
                You can use most of the service without an account. You must be
                at least 13 years old to create one, and creating one requires
                agreeing to these terms and the{" "}
                <a href="/privacy">privacy policy</a>. You are
                responsible for what happens under your account and for keeping
                your sign-in secure. Tell us at <Mail to={HELLO} /> if you think
                someone else is using it.
              </p>
              <p>
                Watch areas are an invite-only trial. We can approve, limit or
                revoke access at any time. Areas are checked about every five
                minutes for incidents, closures, chain controls and fires, and
                delivery is best effort: an alert can be late, missed or wrong,
                so do not depend on one for your safety.
              </p>
              <p>
                You can delete your account at any time, as described in the{" "}
                <a href="/privacy#delete">privacy policy</a>.
              </p>
            </>
          ),
        },
        {
          id: "acceptable-use",
          title: "Acceptable use",
          body: (
            <>
              <p>You agree not to:</p>
              <ul>
                <li>
                  break the law, or use the service to harass, stalk or harm
                  anyone;
                </li>
                <li>
                  post false, misleading, abusive or unlawful reports, or
                  reports that reveal anyone&rsquo;s personal information;
                </li>
                <li>
                  get around rate limits, daily limits, access controls or bot
                  checks, for example by spreading requests across many
                  addresses or accounts;
                </li>
                <li>
                  scrape, crawl or load the service at volumes that degrade it
                  for others, or attack, probe or disrupt it;
                </li>
                <li>
                  use the assistant for anything other than questions about
                  roads, travel and conditions, or try to make it misbehave;
                </li>
                <li>
                  resell access to the hosted service, or present its data as
                  official or as your own; or
                </li>
                <li>
                  use the service for safety-critical or emergency systems,
                  such as dispatch, evacuation or vehicle control.
                </li>
              </ul>
            </>
          ),
        },
        {
          id: "api",
          title: "API, MCP server and API keys",
          body: (
            <>
              <ul>
                <li>
                  <strong>Keys belong to your account.</strong> Keep them
                  secret, never put one in a web page or app that others can
                  read, and revoke any key that may have leaked. A key can read
                  your saved places. You are responsible for requests made with
                  your keys.
                </li>
                <li>
                  <strong>Limits.</strong> Requests with a key count against
                  your account&rsquo;s daily allowance, shared by all of its
                  keys (currently 2,000 a day on the free tier). Requests
                  without a key are limited per network address. Current limits
                  are listed on the <a href="/developers">developer pages</a>.
                  We can change limits at any time.
                </li>
                <li>
                  <strong>Revocation.</strong> We can suspend or revoke a key,
                  or block an address, that breaks these terms or puts the
                  service at risk, with or without notice.
                </li>
                <li>
                  <strong>Showing our data.</strong> If you show data from the
                  service in your own product, credit CommuteScout and the
                  original source, tell your users it can be wrong and to verify
                  with official sources, and do not suggest that we or any
                  agency endorse your product.
                </li>
                <li>
                  <strong>AI assistants.</strong> If you connect the MCP server
                  to an AI assistant, the assistant decides what to ask and how
                  to describe the answers. We are not responsible for what it
                  says, and its provider&rsquo;s terms apply to it.
                </li>
                <li>
                  <strong>No guarantee of availability.</strong> We can change,
                  limit or stop the API, the MCP server or any tool at any time.
                </li>
              </ul>
            </>
          ),
        },
        {
          id: "reports",
          title: "Road reports and other content you post",
          body: (
            <>
              <p>
                Only post reports about what you actually saw, and only when it
                is safe and legal (see <a href="#safety">driving safety</a>).
                Reports are public: they are shown on the map and in our public
                data files without your name or email, and they are sent to the
                plugins you have switched on that accept them, as the{" "}
                <a href="/privacy#recipients">privacy policy</a> describes.
              </p>
              <p>
                You keep any rights you have in what you post. You give us a
                worldwide, non-exclusive, royalty-free license to store, show,
                adapt, publish and share it, including with plugin operators
                and in our public data files, for as long as we need to run the
                service. You confirm that you have the right to post it. We can
                hide or remove any report, for example after other drivers vote
                that it is gone.
              </p>
            </>
          ),
        },
        {
          id: "plugins",
          title: "Plugins and third-party services",
          body: (
            <>
              <p>
                Plugins add alerts from sources other than public agencies, and
                many are run by people other than us. What a plugin shows is
                its operator&rsquo;s, not ours. We list plugins and check that
                they follow the plugin format, but we do not control them, do
                not endorse them, and are not responsible for their content,
                availability or how they handle data.
              </p>
              <p>
                Some plugins have not been reviewed by CommuteScout. You can
                install one, including one you add yourself by address, only
                after you confirm at install that you understand it has not
                been reviewed. Its alerts are then your choice and your risk.
                You can turn any plugin&rsquo;s alerts, and its spoken alerts,
                on or off at any time.
              </p>
              <p>
                The service also relies on other companies, such as sign-in
                providers, app stores, map tile hosts and push notification
                services. Their terms apply to your use of them.
              </p>
            </>
          ),
        },
        {
          id: "apps",
          title: "The CommuteScout Drive apps",
          body: (
            <>
              <p>
                We give you a personal, non-exclusive, revocable license to use
                the apps on devices you own or control, under these terms and
                the open-source license of their code. The terms of the store
                or test program you got an app from also apply.
              </p>
              <h3>Voices</h3>
              <p>
                The apps can download voices that run on your phone. Their
                speech is computer generated. Some voices are based on
                third-party models with their own licenses, which are included
                with each voice download. If a voice is based on the Supertonic
                model, it is licensed under the BigScience OpenRAIL-M license,
                and you agree not to use the voice or anything it generates for
                any use restricted in Attachment A of{" "}
                <a href="https://huggingface.co/Supertone/supertonic-2/blob/main/LICENSE">
                  that license
                </a>
                .
              </p>
              <h3>If you got an app from Apple</h3>
              <ul>
                <li>
                  These terms are between you and us, not Apple. We, not Apple,
                  are responsible for the app and its content.
                </li>
                <li>
                  Apple has no obligation to provide maintenance or support for
                  the app.
                </li>
                <li>
                  To the extent any warranty applies despite the disclaimers
                  below, Apple has no warranty obligation for the app; if the
                  app fails to meet a warranty you may notify Apple, and Apple
                  may refund any purchase price (the app is free).
                </li>
                <li>
                  Apple is not responsible for any claim about the app,
                  including product liability, legal or regulatory compliance,
                  consumer protection, privacy, or intellectual property
                  infringement claims.
                </li>
                <li>
                  You confirm that you are not in a country subject to a US
                  government embargo and are not on any US government list of
                  prohibited or restricted parties.
                </li>
                <li>
                  Apple and its subsidiaries are third-party beneficiaries of
                  these terms and may enforce them against you.
                </li>
              </ul>
            </>
          ),
        },
        {
          id: "open-source",
          title: "Open source and our name",
          body: (
            <p>
              The software is open source under the MIT license at{" "}
              <a href="https://github.com/nicglazkov/commutescout">
                github.com/nicglazkov/commutescout
              </a>{" "}
              and{" "}
              <a href="https://github.com/nicglazkov/commutescout-app">
                github.com/nicglazkov/commutescout-app
              </a>
              . That license governs the code. These terms govern the hosted
              service we run. You are welcome to run your own copy, but please
              do not use the CommuteScout name or logo in a way that suggests it
              is ours or that we endorse it.
            </p>
          ),
        },
        {
          id: "copyright",
          title: "Copyright complaints",
          body: (
            <p>
              Send copyright complaints to <Mail to={HELLO} />. We will review
              them and remove material that should not be here.
            </p>
          ),
        },
        {
          id: "warranty",
          title: "Disclaimer of warranties",
          body: (
            <div className={s.conspicuous}>
              <p>
                THE SERVICE IS PROVIDED &ldquo;AS IS&rdquo; AND &ldquo;AS
                AVAILABLE&rdquo;, WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR
                IMPLIED, INCLUDING ANY IMPLIED WARRANTIES OF MERCHANTABILITY,
                FITNESS FOR A PARTICULAR PURPOSE, ACCURACY, TITLE AND
                NON-INFRINGEMENT.
              </p>
              <p>
                We do not promise that the service or its data will be
                accurate, complete, current, safe, uninterrupted or free of
                errors, that alerts will arrive, or that any route is open,
                legal or safe to drive. Some states do not allow certain
                warranty exclusions, so some of these may not apply to you.
              </p>
            </div>
          ),
        },
        {
          id: "liability",
          title: "Limitation of liability",
          body: (
            <div className={s.conspicuous}>
              <p>
                TO THE FULLEST EXTENT THE LAW ALLOWS, WE ARE NOT LIABLE FOR ANY
                INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY OR
                PUNITIVE DAMAGES, OR FOR LOST PROFITS, DATA, TIME OR GOODWILL,
                ARISING FROM YOUR USE OF OR RELIANCE ON THE SERVICE, ITS DATA,
                ROUTES, ALERTS OR ASSISTANT ANSWERS, EVEN IF WE WERE TOLD THEY
                WERE POSSIBLE.
              </p>
              <p>
                OUR TOTAL LIABILITY FOR ALL CLAIMS ABOUT THE SERVICE IS LIMITED
                TO THE GREATER OF US$50 OR THE AMOUNT YOU PAID US FOR THE
                SERVICE IN THE 12 MONTHS BEFORE THE CLAIM.
              </p>
              <p>
                Nothing in these terms limits liability that the law does not
                allow to be limited, such as liability for fraud, gross
                negligence or willful misconduct, or your rights under laws
                that cannot be waived.
              </p>
            </div>
          ),
        },
        {
          id: "indemnity",
          title: "Indemnity",
          body: (
            <p>
              To the extent the law allows, you agree to defend and compensate
              us for claims, losses and reasonable legal costs brought by third
              parties that arise from your breach of these terms, your misuse
              of the service or your API keys, or content you post.
            </p>
          ),
        },
        {
          id: "termination",
          title: "Suspension and ending access",
          body: (
            <p>
              You can stop using the service at any time and delete your
              account whenever you like. We can suspend or end your access,
              revoke keys, or remove content if you break these terms or put
              the service or others at risk, and we can change or stop the
              service, with or without notice. The sections on reports,
              open source, disclaimers, liability, indemnity, governing law and
              general terms survive the end of your use.
            </p>
          ),
        },
        {
          id: "law",
          title: "Governing law and disputes",
          body: (
            <p>
              These terms are governed by the laws of the State of California
              and applicable US federal law, without regard to conflict-of-law
              rules. If you have a dispute with us, please email{" "}
              <Mail to={HELLO} /> first and give us 30 days to try to resolve
              it informally. If that does not work, either of us may bring the
              dispute in the state or federal courts located in California, or
              in small claims court where it qualifies, and we both consent to
              those courts&rsquo; jurisdiction. If you are a consumer, nothing
              here takes away the protection of mandatory laws of the place
              where you live.
            </p>
          ),
        },
        {
          id: "changes",
          title: "Changes to these terms",
          body: (
            <p>
              We may update these terms. We will post the new version here with
              a new effective date, and for material changes we will email
              account holders before they take effect. If you keep using the
              service after a change takes effect, you accept the updated
              terms. If you do not agree, stop using the service and delete
              your account.
            </p>
          ),
        },
        {
          id: "general",
          title: "General",
          body: (
            <p>
              These terms and the <a href="/privacy">privacy policy</a> are the
              whole agreement between you and us about the service. If any part
              is found unenforceable, the rest still applies. Not enforcing a
              term is not a waiver of it. You may not transfer your rights under
              these terms; we may transfer ours to whoever takes over the
              service. We are not responsible for failures caused by events
              beyond our reasonable control, such as feed or provider outages.
            </p>
          ),
        },
        {
          id: "contact",
          title: "Contact",
          body: (
            <p>
              Questions about these terms: <Mail to={HELLO} />. Privacy
              questions: see the <a href="/privacy">privacy policy</a>.
            </p>
          ),
        },
      ]}
    />
  );
}
