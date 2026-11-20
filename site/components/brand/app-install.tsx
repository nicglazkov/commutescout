import { ANDROID_RELEASES, TESTFLIGHT_PUBLIC } from "@/lib/app-links";

// Install buttons for CommuteScout Drive, one per platform, drawn the same
// way so neither phone is the "main" one. Two lines, like a store badge:
// what you do, then where. Used by the homepage band, /app and the 404.

export type Platform = "ios" | "android";

/** The Apple mark, simplified, at the stroke weight of the lucide set. */
export function AppleGlyph({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="currentColor">
      <path d="M16.37 12.6c-.02-2.2 1.8-3.26 1.88-3.31-1.03-1.5-2.62-1.7-3.18-1.72-1.35-.14-2.64.8-3.33.8-.69 0-1.74-.78-2.87-.76-1.47.02-2.83.86-3.59 2.18-1.53 2.66-.39 6.6 1.1 8.75.73 1.05 1.6 2.24 2.73 2.2 1.1-.05 1.51-.71 2.84-.71 1.32 0 1.7.71 2.86.69 1.18-.02 1.93-1.07 2.65-2.13.84-1.22 1.18-2.4 1.2-2.46-.03-.01-2.3-.88-2.3-3.5ZM14.2 6.13c.6-.73 1.01-1.74.9-2.75-.87.04-1.92.58-2.54 1.31-.56.64-1.05 1.67-.92 2.66.97.07 1.96-.49 2.56-1.22Z" />
    </svg>
  );
}

/** The Android robot's head, simplified. */
export function AndroidGlyph({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="currentColor">
      <path d="M17.6 9.48 19.44 6.3a.38.38 0 0 0-.66-.38l-1.87 3.23A11.5 11.5 0 0 0 12 8.08c-1.77 0-3.43.38-4.91 1.07L5.22 5.92a.38.38 0 0 0-.66.38L6.4 9.48C3.25 11.2 1.1 14.4.8 18h22.4c-.3-3.6-2.45-6.8-5.6-8.52ZM7 15.25a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5Zm10 0a1.25 1.25 0 1 1 0-2.5 1.25 1.25 0 0 1 0 2.5Z" />
    </svg>
  );
}

const COPY: Record<Platform, { href: string; top: string; name: string; Glyph: typeof AppleGlyph; label: string }> = {
  ios: {
    href: TESTFLIGHT_PUBLIC,
    top: "Beta on TestFlight",
    name: "iPhone",
    Glyph: AppleGlyph,
    label: "Install the iPhone beta from TestFlight",
  },
  android: {
    href: ANDROID_RELEASES,
    top: "Download the APK",
    name: "Android",
    Glyph: AndroidGlyph,
    label: "Download the Android APK",
  },
};

/**
 * tone "solid": ink-filled (light page); "band": light on the dark band;
 * "outline": hairline, for secondary placements.
 */
export function InstallButton({
  platform,
  tone = "solid",
  className = "",
}: {
  platform: Platform;
  tone?: "solid" | "band" | "outline";
  className?: string;
}) {
  const { href, top, name, Glyph, label } = COPY[platform];
  const tones = {
    solid: "bg-cs-ink text-cs-bg hover:opacity-90",
    band: "bg-cs-band-ink text-cs-band hover:bg-white",
    outline: "border border-cs-line-strong bg-cs-surface text-cs-ink hover:bg-cs-surface-2",
  } as const;
  return (
    <a
      href={href}
      aria-label={label}
      className={`group inline-flex h-14 min-w-[11.5rem] items-center gap-3 rounded-[var(--cs-radius-md)] px-4 pr-5 transition-[opacity,background-color] duration-150 ${tones[tone]} ${className}`}
    >
      <Glyph className="size-6 shrink-0" />
      <span className="flex flex-col items-start leading-none">
        <span className="text-[0.6875rem] font-medium tracking-[0.01em] opacity-75">{top}</span>
        <span className="mt-1 text-[1.0625rem] font-semibold tracking-[-0.01em]">{name}</span>
      </span>
    </a>
  );
}
