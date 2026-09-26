import type { Metadata } from "next";
import Link from "next/link";
import {
  Apple,
  Bell,
  Megaphone,
  Navigation,
  Puzzle,
  Smartphone,
  UserRound,
  Volume2,
} from "lucide-react";
import { PhoneShot } from "@/components/phone-shot";
import { ANDROID_RELEASES, APP_REPO, TESTFLIGHT_PUBLIC } from "@/lib/app-links";

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

const features = [
  {
    icon: Navigation,
    title: "Turn-by-turn navigation",
    body: "Routes that avoid closures and lane restrictions, with alternates to choose from before you start. Heading-up 3D map, speed limit, and the screen stays on for the trip.",
  },
  {
    icon: Volume2,
    title: "Alerts before you reach them",
    body: "Incidents, closures, chain controls and community reports along your route, spoken a distance ahead that you set per kind.",
  },
  {
    icon: Megaphone,
    title: "Reports from the road",
    body: "One tap to report police, a crash, a hazard or a closure. Reports snap to the road and show on this site and in every app.",
  },
  {
    icon: Puzzle,
    title: "Plugins",
    body: "Turn on community sources from the catalog, or add a private plugin by URL. Every alert says where it came from, and what a plugin sees is yours alone.",
  },
  {
    icon: UserRound,
    title: "The same account",
    body: "Sign in with Google or Apple. Your watch areas, saved places and plugin choices follow you between the web and the phone.",
  },
  {
    icon: Bell,
    title: "Watch areas on the phone",
    body: "The areas you drew on the web map notify the phone too: a push when something new appears inside one.",
  },
];

// Every screenshot: captured from the simulator and the emulator with a
// simulated location and a demo status bar (scripts/capture_app_shots.sh),
// so they show the app and nothing about anybody.
const gallery = [
  {
    src: "/shots/app/ios-nav.webp",
    alt: "iPhone: navigating along a waterfront street with the next turn, the speed limit and the arrival time",
    caption: "Drive. The next turn, the speed limit, and when you arrive.",
  },
  {
    src: "/shots/app/android-nav.webp",
    alt: "Android: a route with a closure ahead shown in an alert strip above the arrival time",
    caption: "Hear it first. A closure ahead, read out before you get there.",
  },
  {
    src: "/shots/app/ios-alert.webp",
    alt: "iPhone: a hazard reported on the route, shown in an alert strip with how far ahead it is",
    caption: "Know what is ahead. Every alert says how far, and how many more.",
  },
  {
    src: "/shots/app/ios-map.webp",
    alt: "iPhone: the live map around the driver with a closed road segment, a camera and a report",
    caption: "Look around. The same live map as the site, around you.",
  },
];

export default function AppPage() {
  return (
    <>
      {/* Hero: the pitch and the two install links beside the app itself. */}
      <section className="relative overflow-hidden bg-cs-navy text-white">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-32 top-0 h-[48rem] w-[48rem] rounded-full bg-cs-sky/25 blur-3xl"
        />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-6 py-16 md:grid-cols-[1.1fr_1fr] md:items-center md:py-24">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white/80 ring-1 ring-white/15">
              <Smartphone className="size-3.5" aria-hidden />
              Early access
            </p>
            <h1 className="mt-5 text-balance text-4xl font-medium tracking-tight md:text-6xl">
              CommuteScout Drive.
              <br />
              The live map, with a voice.
            </h1>
            <p className="mt-5 max-w-xl text-balance text-lg text-white/70">
              Turn-by-turn navigation for iPhone and Android that reads the same official feeds as
              this site: closures, chain controls, crashes and community reports, spoken before you
              reach them. Same account, same plugins, one tap to report what you see.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href={TESTFLIGHT_PUBLIC}
                className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-cs-navy transition-colors hover:bg-white/90"
              >
                <Apple className="size-4" aria-hidden />
                iPhone: join the TestFlight beta
              </a>
              <a
                href={ANDROID_RELEASES}
                className="inline-flex items-center gap-2 rounded-full border border-white/30 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
              >
                <Smartphone className="size-4" aria-hidden />
                Android: download the APK
              </a>
            </div>
            <p className="mt-4 text-sm text-white/50">
              Free while in beta. Open the link on your phone: TestFlight installs the iPhone build,
              and the Android build installs from the release page.
            </p>
          </div>

          <div className="flex items-end justify-center gap-4 sm:gap-6 md:justify-end">
            <PhoneShot
              src="/shots/app/android-nav.webp"
              alt="CommuteScout Drive on Android with a closure alert ahead on the route"
              width={210}
              className="hidden sm:block"
            />
            <PhoneShot
              src="/shots/app/ios-nav.webp"
              alt="CommuteScout Drive on iPhone navigating with the next turn, the speed limit and the arrival time"
              width={280}
              priority
            />
          </div>
        </div>
      </section>

      {/* What it does. */}
      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-7xl px-6">
          <h2 className="text-balance text-3xl font-medium tracking-tight text-cs-ink md:text-4xl">
            Everything the map knows, while you drive.
          </h2>
          <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, body }) => (
              <div key={title} className="rounded-2xl border border-cs-line bg-cs-paper p-6">
                <div className="inline-flex size-10 items-center justify-center rounded-xl bg-cs-sky/10 text-cs-sky">
                  <Icon className="size-5" aria-hidden />
                </div>
                <h3 className="mt-4 font-semibold text-cs-ink">{title}</h3>
                <p className="mt-2 text-sm text-cs-ink/70">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Screens. A row of phones that scrolls sideways on a phone and
          fits four across on a desktop. */}
      <section className="overflow-hidden bg-cs-bg py-16 md:py-20">
        <div className="mx-auto max-w-7xl px-6">
          <h2 className="text-balance text-3xl font-medium tracking-tight text-cs-ink md:text-4xl">
            On the road
          </h2>
          <p className="mt-3 max-w-2xl text-cs-ink/70">
            Screens from the apps, on a simulated drive. Alerts, times and distances are what the
            app showed at the time.
          </p>
        </div>
        <div className="mt-10 flex snap-x snap-mandatory gap-6 overflow-x-auto px-6 pb-4 md:mx-auto md:max-w-7xl md:justify-between">
          {gallery.map(({ src, alt, caption }) => (
            <figure key={src} className="snap-center shrink-0" style={{ width: 240 }}>
              <PhoneShot src={src} alt={alt} width={240} />
              <figcaption className="mt-4 text-sm text-cs-ink/70">{caption}</figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* Install. */}
      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-7xl px-6">
          <h2 className="text-balance text-3xl font-medium tracking-tight text-cs-ink md:text-4xl">
            Install
          </h2>
          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div className="rounded-2xl border border-cs-line bg-cs-paper p-6">
              <div className="flex items-center gap-2">
                <Apple className="size-5 text-cs-ink" aria-hidden />
                <h3 className="font-semibold text-cs-ink">iPhone</h3>
              </div>
              <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-cs-ink/80">
                <li>Install TestFlight from the App Store.</li>
                <li>
                  Open the{" "}
                  <a href={TESTFLIGHT_PUBLIC} className="font-medium text-cs-sky hover:underline">
                    public beta link
                  </a>{" "}
                  on your phone and tap Install.
                </li>
                <li>Updates arrive through TestFlight.</li>
              </ol>
              <a
                href={TESTFLIGHT_PUBLIC}
                className="mt-5 inline-flex items-center gap-2 rounded-full bg-cs-navy px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-cs-navy/90"
              >
                <Apple className="size-4" aria-hidden />
                Join the TestFlight beta
              </a>
            </div>
            <div className="rounded-2xl border border-cs-line bg-cs-paper p-6">
              <div className="flex items-center gap-2">
                <Smartphone className="size-5 text-cs-ink" aria-hidden />
                <h3 className="font-semibold text-cs-ink">Android</h3>
              </div>
              <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-cs-ink/80">
                <li>
                  Open the{" "}
                  <a href={ANDROID_RELEASES} className="font-medium text-cs-sky hover:underline">
                    latest release
                  </a>{" "}
                  on your phone and download the APK.
                </li>
                <li>Open the file and allow installing from that source when asked.</li>
                <li>New versions are new APKs on the same page; install over the old one.</li>
              </ol>
              <a
                href={ANDROID_RELEASES}
                className="mt-5 inline-flex items-center gap-2 rounded-full bg-cs-navy px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-cs-navy/90"
              >
                <Smartphone className="size-4" aria-hidden />
                Download the APK
              </a>
            </div>
          </div>
          <p className="mt-8 max-w-3xl text-sm text-cs-ink/70">
            Both apps are open source at{" "}
            <a href={APP_REPO} className="text-cs-sky hover:underline">
              github.com/nicglazkov/commutescout-app
            </a>
            . Location stays on the phone except for what a route or a report needs, and what a
            plugin sees is served to you alone; see{" "}
            <Link href="/privacy" prefetch={false} className="text-cs-sky hover:underline">
              Privacy
            </Link>
            .
          </p>
        </div>
      </section>
    </>
  );
}
