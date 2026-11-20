import type { Metadata } from "next";
import Link from "next/link";
import {
  Bell,
  Download,
  Link2,
  Megaphone,
  Navigation,
  Puzzle,
  RefreshCw,
  ShieldCheck,
  UserRound,
  Volume2,
  type LucideIcon,
} from "lucide-react";
import { PhoneShot } from "@/components/phone-shot";
import { BrandMark } from "@/components/brand/brand-mark";
import { AndroidGlyph, AppleGlyph, InstallButton, type Platform } from "@/components/brand/app-install";
import { PlatformPair } from "@/components/brand/platform-pair";
import shots from "@/public/shots/app/shots.json";
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
// simulated location and a demo status bar, so they show the app and
// nothing about anybody. `scripts/capture_app_shots.sh --install out/`
// recaptures all five, copies them into public/shots/app/ and rewrites
// public/shots/app/shots.json (app version, date), which the caption under
// the gallery prints; `--check` says whether they trail the newest release.
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

// "Captured September 2026, version 0.6.0" from shots.json.
function capturedLine(): string {
  const d = new Date(`${shots.captured}T12:00:00Z`);
  const when = d.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
  return shots.app_version ? `Captured ${when} from version ${shots.app_version}.` : `Captured ${when}.`;
}

type Step = { icon: LucideIcon; text: React.ReactNode };

const INSTALL: Record<Platform, { name: string; sub: string; Glyph: typeof AppleGlyph; steps: Step[]; note: string | null }> = {
  ios: {
    name: "iPhone",
    sub: "Public beta on TestFlight",
    Glyph: AppleGlyph,
    steps: [
      { icon: Download, text: <>Install TestFlight from the App Store.</> },
      {
        icon: Link2,
        text: (
          <>
            Open the{" "}
            <a href={TESTFLIGHT_PUBLIC} className="cs-link">
              public beta link
            </a>{" "}
            on your phone and tap Install.
          </>
        ),
      },
      { icon: RefreshCw, text: <>Updates arrive through TestFlight.</> },
    ],
    note: TESTFLIGHT_IN_REVIEW ? TESTFLIGHT_IN_REVIEW_NOTE : null,
  },
  android: {
    name: "Android",
    sub: "APK from the GitHub release",
    Glyph: AndroidGlyph,
    steps: [
      {
        icon: Download,
        text: (
          <>
            Open the{" "}
            <a href={ANDROID_RELEASES} className="cs-link">
              latest release
            </a>{" "}
            on your phone and download the APK.
          </>
        ),
      },
      { icon: ShieldCheck, text: <>Open the file and allow installing from that source when asked.</> },
      { icon: RefreshCw, text: <>New versions appear on the same page. Install them over the old one.</> },
    ],
    note: null,
  },
};

// One platform's install card: a tinted header with the platform, then the
// steps on a numbered rail, then the button. Both cards are identical in
// weight; PlatformPair puts the visitor's own phone first.
function InstallCard({ platform }: { platform: Platform }) {
  const { name, sub, Glyph, steps, note } = INSTALL[platform];
  return (
    <article className="flex h-full flex-col overflow-hidden rounded-[calc(var(--cs-radius-lg)+4px)] border border-cs-line bg-cs-surface shadow-[var(--cs-shadow-sm)] in-data-[yours]:border-cs-accent in-data-[yours]:shadow-[var(--cs-shadow-md)]">
      <header className="flex items-center gap-4 border-b border-cs-line bg-cs-accent-soft px-6 py-5 md:px-8">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-[var(--cs-radius-md)] bg-cs-accent text-cs-accent-ink shadow-[var(--cs-shadow-sm)]">
          <Glyph className="size-6" />
        </span>
        <div>
          <h3 className="text-[1.25rem] font-semibold leading-tight tracking-[-0.015em] text-cs-ink">{name}</h3>
          <p className="mt-0.5 text-sm text-cs-ink-2">{sub}</p>
        </div>
      </header>
      <ol className="flex-1 px-6 py-7 md:px-8">
        {steps.map(({ icon: Icon, text }, i) => (
          <li key={i} className="relative flex gap-4 pb-7 last:pb-0">
            {/* The rail joining the step numbers. */}
            {i < steps.length - 1 && (
              <span aria-hidden className="absolute bottom-0 left-[17px] top-10 w-0.5 rounded-full bg-cs-accent-soft" />
            )}
            <span className="cs-data relative flex size-9 shrink-0 items-center justify-center rounded-full bg-cs-accent text-sm font-semibold text-cs-accent-ink">
              {i + 1}
            </span>
            <div className="flex min-w-0 flex-1 items-start gap-3 rounded-[var(--cs-radius-md)] border border-cs-line bg-cs-bg px-4 py-3">
              <Icon aria-hidden className="mt-0.5 size-[18px] shrink-0 text-cs-accent" strokeWidth={1.75} />
              <p className="text-[0.9375rem] leading-relaxed text-cs-ink">{text}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="px-6 pb-7 md:px-8">
        {note && <p className="mb-4 text-sm text-cs-ink-3">{note}</p>}
        <InstallButton platform={platform} />
      </div>
    </article>
  );
}

export default function AppPage() {
  return (
    <>
      {/* Hero, on the site's dark band: the pitch, one install button per
          platform (equal weight; the visitor's own phone first), and one
          real screenshot from each platform rising off the band's edge. */}
      <section className="overflow-hidden border-b border-cs-band-line bg-cs-band text-cs-band-ink">
        <div className="cs-container grid grid-cols-1 items-center gap-12 pt-14 md:pt-20 lg:grid-cols-12 lg:gap-10">
          <div className="pb-4 lg:col-span-6 lg:pb-24">
            <div className="cs-rise flex items-center gap-3">
              <BrandMark className="size-12" />
              <span className="cs-data rounded-full border border-cs-band-line px-2.5 py-1 text-xs uppercase tracking-[0.08em] text-cs-band-ink-2">
                Free while in beta
              </span>
            </div>
            <h1 className="cs-display cs-rise mt-7 text-cs-band-ink [animation-delay:60ms]">CommuteScout Drive</h1>
            <p className="cs-lede cs-rise mt-6 max-w-[34rem] text-cs-band-ink-2 [animation-delay:120ms]">
              Turn-by-turn navigation for iPhone and Android. It reads out closures, chain controls,
              crashes and reports on your route before you reach them.
            </p>
            <PlatformPair
              className="cs-rise mt-9 flex flex-wrap gap-3 [animation-delay:180ms]"
              badgeClassName="-top-2.5 right-2"
              ios={<InstallButton platform="ios" tone="band" />}
              android={<InstallButton platform="android" tone="band" />}
            />
            <p className="cs-rise mt-5 max-w-[36rem] text-sm text-cs-band-ink-2 [animation-delay:240ms]">
              Open this page on your phone to install. Steps for each phone are{" "}
              <a href="#install" className="text-cs-band-ink underline decoration-cs-band-line underline-offset-4 hover:decoration-cs-band-ink">
                just below
              </a>
              .
            </p>
            {TESTFLIGHT_IN_REVIEW && <p className="mt-2 text-sm text-cs-band-ink-2">{TESTFLIGHT_IN_REVIEW_NOTE}</p>}
          </div>

          <div className="min-w-0 lg:col-span-6 lg:self-end">
            <div className="mx-auto flex max-w-[34rem] items-start justify-center gap-5 sm:gap-7">
              <PhoneShot
                src="/shots/app/ios-nav.webp"
                alt="CommuteScout Drive on iPhone navigating with the next turn, the speed limit and the arrival time"
                width={250}
                priority
                className="-mb-16 w-[46%] lg:-mb-24"
              />
              <PhoneShot
                src="/shots/app/android-nav.webp"
                alt="CommuteScout Drive on Android with a closure alert ahead on the route"
                width={250}
                className="-mb-28 mt-12 w-[46%] lg:-mb-36"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Install, right under the hero: one card per phone. */}
      <section id="install" aria-labelledby="install-title" className="scroll-mt-20 bg-cs-surface-2/60 py-20 md:py-24">
        <div className="cs-container">
          <div className="max-w-[40rem]">
            <p className="cs-eyebrow">Install</p>
            <h2 id="install-title" className="cs-h2 mt-3">
              Three steps on either phone
            </h2>
          </div>
          <PlatformPair
            className="mt-10 grid gap-5 md:grid-cols-2 md:gap-6"
            badgeClassName="-top-2.5 right-5"
            ios={<InstallCard platform="ios" />}
            android={<InstallCard platform="android" />}
          />
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

      {/* What it does: an indexed grid, hairlines instead of cards. */}
      <section aria-labelledby="does-title" className="border-t border-cs-line bg-cs-surface py-20 md:py-28">
        <div className="cs-container">
          <h2 id="does-title" className="cs-h2">
            Features
          </h2>
          <ul className="mt-12 grid gap-x-10 sm:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, body }) => (
              <li key={title} className="border-t border-cs-line py-8">
                <span className="flex size-10 items-center justify-center rounded-[var(--cs-radius-md)] bg-cs-accent-soft text-cs-accent">
                  <Icon aria-hidden className="size-5" strokeWidth={1.75} />
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
          <p className="cs-lede mt-4 max-w-[40rem]">Taken on a simulated drive. {capturedLine()}</p>
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
    </>
  );
}
