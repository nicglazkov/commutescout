import Link from "next/link";
import { Apple, ArrowRight, Smartphone } from "lucide-react";
import { PhoneShot } from "@/components/phone-shot";
import { ANDROID_RELEASES, TESTFLIGHT_PUBLIC } from "@/lib/app-links";

// The phone apps, right under the homepage hero, so anyone landing on
// the site sees them before the feature list. Two phones from the real
// apps (a drive in progress on iPhone, the live map on Android) and the
// two install links. Everything else about the apps is on /app.
export default function AppBand() {
  return (
    <section className="relative overflow-hidden bg-cs-navy text-white">
      {/* A soft glow behind the phones so they read as lit objects on the
          dark band rather than pasted on. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 top-1/2 h-[42rem] w-[42rem] -translate-y-1/2 rounded-full bg-cs-sky/25 blur-3xl"
      />
      <div className="relative mx-auto grid max-w-7xl gap-12 px-6 py-16 md:grid-cols-2 md:items-center md:py-24">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white/80 ring-1 ring-white/15">
            <Smartphone className="size-3.5" aria-hidden />
            New: iPhone and Android
          </p>
          <h2 className="mt-5 text-balance text-4xl font-medium tracking-tight md:text-5xl">
            Take the live map on the road.
          </h2>
          <p className="mt-5 max-w-md text-balance text-lg text-white/70">
            CommuteScout Drive is turn-by-turn navigation with the same official alerts as this
            site, spoken before you reach them. Closures, chain controls and crashes ahead, one-tap
            reports from the road, and the same account as the web.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href={TESTFLIGHT_PUBLIC}
              className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-cs-navy transition-colors hover:bg-white/90"
            >
              <Apple className="size-4" aria-hidden />
              iPhone beta on TestFlight
            </a>
            <a
              href={ANDROID_RELEASES}
              className="inline-flex items-center gap-2 rounded-full border border-white/30 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
            >
              <Smartphone className="size-4" aria-hidden />
              Android APK
            </a>
          </div>
          <Link
            href="/app"
            prefetch={false}
            className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-white/80 underline-offset-4 transition-colors hover:text-white hover:underline"
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
