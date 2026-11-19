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
import {
  ANDROID_RELEASES,
  APP_REPO,
  TESTFLIGHT_IN_REVIEW,
  TESTFLIGHT_IN_REVIEW_NOTE,
  TESTFLIGHT_PUBLIC,
} from "@/lib/app-links";

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
    body: "Routes around closures and lane restrictions, with alternate routes to pick from before you start. Shows the speed limit and keeps the screen on.",
  },
  {
    icon: Volume2,
    title: "Spoken alerts",
    body: "Incidents, closures, chain controls and reports on your route are read out before you reach them. You set how far ahead for each kind.",
  },
  {
    icon: Megaphone,
    title: "Reports",
    body: "Tap to report police, a crash, a hazard or a closure. Your report shows on the map on this site and in the apps.",
  },
  {
    icon: Puzzle,
    title: "Plugins",
    body: "Turn on plugins from the catalog, or add a private one by its address. Each alert shows which plugin sent it.",
  },
  {
    icon: UserRound,
    title: "One account",
    body: "Sign in with Google or Apple. Your watch areas, saved places and plugins are the same on the web and the phone.",
  },
  {
    icon: Bell,
    title: "Watch areas",
    body: "Get a push notification when something new appears in a watch area you drew on the web map.",
  },
];

// Every screenshot: captured from the simulator and the emulator with a
// simulated location and a demo status bar (scripts/capture_app_shots.sh),
// so they show the app and nothing about anybody.
const gallery = [
  {
    src: "/shots/app/ios-nav.webp",
    alt: "iPhone: navigating along a waterfront street with the next turn, the speed limit and the arrival time",
    caption: "The next turn, the speed limit and the arrival time.",
  },
  {
    src: "/shots/app/android-nav.webp",
    alt: "Android: a route with a closure ahead shown in an alert strip above the arrival time",
    caption: "A closure ahead on the route.",
  },
  {
    src: "/shots/app/ios-alert.webp",
    alt: "iPhone: a hazard reported on the route, shown in an alert strip with how far ahead it is",
    caption: "A reported hazard ahead, with its distance.",
  },
  {
    src: "/shots/app/ios-map.webp",
    alt: "iPhone: the live map around the driver with a closed road segment, a camera and a report",
    caption: "The live map around you.",
  },
];

const installBtn =
  "inline-flex h-11 items-center gap-2 rounded-[var(--cs-radius-md)] px-4 text-[0.9375rem] font-medium transition-colors duration-150";

export default function AppPage() {
  return (
    <>
      {/* Hero: the pitch and both install links beside the app itself. */}
      <section className="overflow-hidden">
        <div className="cs-container grid items-center gap-14 pb-16 pt-12 md:pb-24 md:pt-20 lg:grid-cols-12 lg:gap-10">
          <div className="lg:col-span-6">
            <h1 className="cs-display cs-rise">CommuteScout Drive</h1>
            <p className="cs-lede cs-rise mt-6 max-w-[34rem] [animation-delay:120ms]">
              Turn-by-turn navigation for iPhone and Android. It reads out closures, chain controls,
              crashes and reports on your route before you reach them.
            </p>
            <div className="cs-rise mt-8 flex flex-wrap gap-3 [animation-delay:180ms]">
              <a href={TESTFLIGHT_PUBLIC} className={`${installBtn} bg-cs-accent text-cs-accent-ink shadow-[var(--cs-shadow-sm)] hover:bg-cs-accent-hover`}>
                <Apple aria-hidden className="size-4" />
                iPhone: join the TestFlight beta
              </a>
              <a href={ANDROID_RELEASES} className={`${installBtn} border border-cs-line-strong bg-cs-surface text-cs-ink hover:bg-cs-surface-2`}>
                <Smartphone aria-hidden className="size-4" />
                Android: download the APK
              </a>
            </div>
            <p className="cs-rise mt-5 max-w-[36rem] text-sm text-cs-ink-3 [animation-delay:240ms]">
              Free while in beta. Open the link on your phone to install.
            </p>
            {TESTFLIGHT_IN_REVIEW && <p className="mt-2 text-sm text-cs-ink-2">{TESTFLIGHT_IN_REVIEW_NOTE}</p>}
          </div>

          <div className="lg:col-span-6">
            <div className="relative mx-auto flex max-w-[34rem] items-end justify-center gap-5 sm:gap-7">
              <PhoneShot
                src="/shots/app/android-nav.webp"
                alt="CommuteScout Drive on Android with a closure alert ahead on the route"
                width={230}
                className="mb-12 hidden sm:block"
              />
              <PhoneShot
                src="/shots/app/ios-nav.webp"
                alt="CommuteScout Drive on iPhone navigating with the next turn, the speed limit and the arrival time"
                width={260}
                priority
              />
            </div>
          </div>
        </div>
      </section>

      {/* What it does: an indexed grid, hairlines instead of cards. */}
      <section aria-labelledby="does-title" className="border-t border-cs-line bg-cs-surface py-20 md:py-28">
        <div className="cs-container">
          <h2 id="does-title" className="cs-h2">
            Features
          </h2>
          <ul className="mt-12 grid gap-x-10 sm:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, body }) => (
              <li key={title} className="border-t border-cs-line py-8">
                <span className="flex size-9 items-center justify-center rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-bg text-cs-accent">
                  <Icon aria-hidden className="size-[18px]" strokeWidth={1.75} />
                </span>
                <h3 className="cs-h3 mt-5">{title}</h3>
                <p className="mt-2 max-w-[38ch] text-[0.9375rem] leading-relaxed text-cs-ink-2">{body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Screens: scrolls sideways on a phone, four across on a desktop. */}
      <section aria-labelledby="screens-title" className="border-t border-cs-line py-20 md:py-28">
        <div className="cs-container">
          <h2 id="screens-title" className="cs-h2">Screenshots</h2>
          <p className="cs-lede mt-4 max-w-[40rem]">Taken on a simulated drive.</p>
        </div>
        <div className="cs-container mt-12">
          <ul className="-mx-5 flex snap-x snap-mandatory gap-5 overflow-x-auto px-5 pb-4 md:mx-0 md:grid md:grid-cols-4 md:gap-6 md:overflow-visible md:px-0">
            {gallery.map(({ src, alt, caption }) => (
              <li key={src} className="w-[62vw] max-w-[15rem] shrink-0 snap-center md:w-auto md:max-w-none">
                <figure>
                  <PhoneShot src={src} alt={alt} width={300} className="w-full" />
                  <figcaption className="mt-4 text-sm leading-relaxed text-cs-ink-2">{caption}</figcaption>
                </figure>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Install. */}
      <section aria-labelledby="install-title" className="border-t border-cs-line bg-cs-surface py-20 md:py-28">
        <div className="cs-container">
          <h2 id="install-title" className="cs-h2">Install</h2>
          <div className="mt-12 grid gap-4 md:grid-cols-2 md:gap-6">
            {[
              {
                icon: Apple,
                name: "iPhone",
                steps: [
                  <>Install TestFlight from the App Store.</>,
                  <>
                    Open the{" "}
                    <a href={TESTFLIGHT_PUBLIC} className="cs-link">
                      public beta link
                    </a>{" "}
                    on your phone and tap Install.
                  </>,
                  <>Updates arrive through TestFlight.</>,
                ],
                href: TESTFLIGHT_PUBLIC,
                cta: "Join the TestFlight beta",
                note: TESTFLIGHT_IN_REVIEW ? TESTFLIGHT_IN_REVIEW_NOTE : null,
              },
              {
                icon: Smartphone,
                name: "Android",
                steps: [
                  <>
                    Open the{" "}
                    <a href={ANDROID_RELEASES} className="cs-link">
                      latest release
                    </a>{" "}
                    on your phone and download the APK.
                  </>,
                  <>Open the file and allow installing from that source when asked.</>,
                  <>New versions appear on the same page. Install them over the old one.</>,
                ],
                href: ANDROID_RELEASES,
                cta: "Download the APK",
                note: null,
              },
            ].map(({ icon: Icon, name, steps, href, cta, note }) => (
              <div key={name} className="flex flex-col rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-bg p-6 md:p-8">
                <div className="flex items-center gap-2.5">
                  <Icon aria-hidden className="size-5 text-cs-ink" />
                  <h3 className="cs-h3">{name}</h3>
                </div>
                <ol className="mt-6 flex-1 space-y-4">
                  {steps.map((step, i) => (
                    <li key={i} className="flex gap-3.5 text-[0.9375rem] leading-relaxed text-cs-ink-2">
                      <span aria-hidden className="cs-data mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border border-cs-line-strong text-xs text-cs-ink">
                        {i + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
                {note && <p className="mt-4 text-sm text-cs-ink-3">{note}</p>}
                <a href={href} className={`${installBtn} mt-8 w-fit border border-cs-line-strong bg-cs-surface text-cs-ink hover:bg-cs-surface-2`}>
                  <Icon aria-hidden className="size-4" />
                  {cta}
                </a>
              </div>
            ))}
          </div>
          <p className="mt-10 max-w-[44rem] text-[0.9375rem] leading-relaxed text-cs-ink-2">
            Both apps are open source at{" "}
            <a href={APP_REPO} className="cs-link">
              github.com/nicglazkov/commutescout-app
            </a>
            . Your location stays on the phone, except what a route or a report needs. Details are
            in the{" "}
            <Link href="/privacy" prefetch={false} className="cs-link">
              Privacy Policy
            </Link>
            .
          </p>
        </div>
      </section>
    </>
  );
}
