import Link from "next/link";
import { Apple, ArrowRight, Smartphone } from "lucide-react";
import { PhoneShot } from "@/components/phone-shot";
import {
  ANDROID_RELEASES,
  TESTFLIGHT_IN_REVIEW,
  TESTFLIGHT_IN_REVIEW_NOTE,
  TESTFLIGHT_PUBLIC,
} from "@/lib/app-links";

// The phone apps, right under the homepage hero, so anyone landing on
// the site sees them before the feature list. Two phones from the real
// apps (a drive in progress on iPhone, the live map on Android) and the
// two install links. Everything else about the apps is on /app.
export default function AppBand() {
  return (
    <section className="relative overflow-hidden border-y border-cs-line bg-cs-navy/70">
      {/* A soft glow behind the phones so they read as lit objects on the
          dark band rather than pasted on. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 top-1/2 h-[42rem] w-[42rem] -translate-y-1/2 rounded-full bg-[#ff9a3c]/15 blur-3xl"
      />
      <div className="relative mx-auto grid max-w-7xl gap-12 px-6 py-16 md:grid-cols-2 md:items-center md:py-24">
        <div>
          <p className="eyebrow inline-flex items-center gap-2">
            <Smartphone className="size-3.5" aria-hidden />
            New: iPhone and Android
          </p>
          <h2 className="mt-5">
            Take the live map on the road.
          </h2>
          <p className="mt-5 max-w-[48ch] text-lg leading-relaxed text-cs-muted">
            CommuteScout Drive is turn-by-turn navigation with the same official alerts as this
            site, spoken before you reach them. Closures, chain controls and crashes ahead, one-tap
            reports from the road, and the same account as the web.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href={TESTFLIGHT_PUBLIC}
              className="inline-flex h-11 items-center gap-2 rounded-[var(--site-radius)] bg-cs-sky px-5 text-sm font-bold text-cs-on-sky shadow-[0_0_32px_-8px_var(--cs-sky)] transition-colors hover:bg-cs-sky/90"
            >
              <Apple className="size-4" aria-hidden />
              iPhone beta on TestFlight
            </a>
            <a
              href={ANDROID_RELEASES}
              className="inline-flex h-11 items-center gap-2 rounded-[var(--site-radius)] bg-cs-ink/[0.07] px-5 text-sm font-semibold text-cs-ink ring-1 ring-cs-line transition-colors hover:bg-cs-ink/[0.12]"
            >
              <Smartphone className="size-4" aria-hidden />
              Android APK
            </a>
          </div>
          {TESTFLIGHT_IN_REVIEW && (
            <p className="mt-4 max-w-md text-sm text-cs-muted">{TESTFLIGHT_IN_REVIEW_NOTE}</p>
          )}
          <Link
            href="/app"
            prefetch={false}
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-cs-sky underline-offset-4 hover:underline"
          >
            See what the app does
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>

        <div className="flex justify-center md:justify-end">
          <div className="flex items-end gap-4 sm:gap-6">
            <PhoneShot
              src="/shots/app/android-map.webp"
              alt="CommuteScout Drive on Android showing the live map with a closure near the driver"
              width={200}
              className="hidden sm:block"
            />
            <PhoneShot
              src="/shots/app/ios-nav.webp"
              alt="CommuteScout Drive on iPhone navigating a route with the next turn, the speed limit and the arrival time"
              width={260}
              priority
            />
          </div>
        </div>
      </div>
    </section>
  );
}
