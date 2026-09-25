import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Get the app - CommuteScout",
  description:
    "CommuteScout Drive for iPhone and Android: turn-by-turn navigation with live road alerts from every state's DOT feeds, spoken ahead of time, and reports from the road.",
  alternates: { canonical: "https://commutescout.com/app" },
  openGraph: {
    title: "Get the app - CommuteScout",
    description:
      "CommuteScout Drive for iPhone and Android: turn-by-turn navigation with live road alerts from every state's DOT feeds, spoken ahead of time, and reports from the road.",
    url: "https://commutescout.com/app",
    images: ["/static/shots/og.png"],
  },
  twitter: { card: "summary_large_image", images: ["/static/shots/og.png"] },
};

const ANDROID_RELEASES = "https://github.com/nicglazkov/commutescout-app/releases/latest";
// The public TestFlight group; anyone with the link can install the beta.
const TESTFLIGHT_PUBLIC = "https://testflight.apple.com/join/1CbutYdy";
const APP_REPO = "https://github.com/nicglazkov/commutescout-app";

const features = [
  ["Turn-by-turn navigation", "Routes from Stadia Maps with lane closures and full closures avoided. Alternates to choose from before you start."],
  ["Alerts before you reach them", "Incidents, closures, chain controls and community reports along your route, spoken a distance ahead that you set per kind."],
  ["Reports from the road", "One tap to report police, a crash, a hazard or a closure. Reports snap to the road and show on this site and in every app."],
  ["The same account", "Sign in with Google or Apple. Your watch areas, saved places and plugin choices follow you between the web and the phone."],
  ["Plugins", "Turn on community sources from the catalog, or add a private plugin by URL. Every alert says where it came from."],
  ["Heads-up while driving", "Heading-up 3D map, speed limit, a collapsible strip for the next alert, and the screen stays on for the trip."],
];

export default function AppPage() {
  return (
    <>
      <section className="bg-cs-navy text-white">
        <div className="mx-auto max-w-7xl px-6 py-16 md:py-24">
          <p className="text-sm font-medium uppercase tracking-wider text-white/60">New</p>
          <h1 className="mt-2 text-balance text-4xl font-medium tracking-tight md:text-5xl">
            CommuteScout Drive, for iPhone and Android.
          </h1>
          <p className="text-white/70 mt-4 max-w-2xl text-balance text-lg">
            The live map, as a navigation app. Same alerts, same account, same plugins, with a
            voice that tells you what is ahead before you get there.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href={TESTFLIGHT_PUBLIC}
              className="rounded-full bg-white px-5 py-2.5 text-sm font-medium text-cs-navy transition-colors hover:bg-white/90"
            >
              iPhone: join the TestFlight beta
            </a>
            <a
              href={ANDROID_RELEASES}
              className="rounded-full border border-white/30 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-white/10"
            >
              Android: download the APK
            </a>
          </div>
          <p className="text-white/50 mt-4 text-sm">
            Early access. The iPhone build is a public TestFlight beta: open the link on your phone and
            tap Install. The Android build installs from the release page.
          </p>
        </div>
      </section>

      <section className="py-14 md:py-16">
        <div className="mx-auto max-w-7xl px-6">
          <h2 className="text-2xl font-semibold tracking-tight text-cs-ink md:text-3xl">What it does</h2>
          <div className="mt-8 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {features.map(([title, body]) => (
              <div key={title} className="rounded-2xl border border-cs-ink/10 bg-white p-6">
                <h3 className="font-semibold text-cs-ink">{title}</h3>
                <p className="text-cs-ink/70 mt-2 text-sm">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-cs-bg py-14 md:py-16">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="text-2xl font-semibold tracking-tight text-cs-ink md:text-3xl">Install</h2>
          <div className="mt-6 space-y-6 text-cs-ink/80">
            <div>
              <h3 className="font-semibold text-cs-ink">iPhone</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
                <li>Install TestFlight from the App Store.</li>
                <li>
                  Open the{" "}
                  <a href={TESTFLIGHT_PUBLIC} className="text-cs-sky hover:underline">
                    public beta link
                  </a>{" "}
                  on your phone and tap Install. Updates arrive through TestFlight.
                </li>
              </ol>
            </div>
            <div>
              <h3 className="font-semibold text-cs-ink">Android</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
                <li>
                  Open the{" "}
                  <a href={ANDROID_RELEASES} className="text-cs-sky hover:underline">
                    latest release
                  </a>{" "}
                  on your phone and download the APK.
                </li>
                <li>Open the file and allow installing from that source when asked.</li>
                <li>New versions are new APKs on the same page; install over the old one.</li>
              </ol>
            </div>
            <p className="text-sm">
              Both apps are open source at{" "}
              <a href={APP_REPO} className="text-cs-sky hover:underline">
                github.com/nicglazkov/commutescout-app
              </a>
              . Location stays on the phone except for what a route or a report needs; see{" "}
              <Link href="/privacy" prefetch={false} className="text-cs-sky hover:underline">
                Privacy
              </Link>
              .
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
