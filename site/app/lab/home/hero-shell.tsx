import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";

// The live hero's left column, copied as it stands in
// components/blocks/hero-section-1.tsx (links are inert here), with a slot
// on the right for the option. Same grid, same widths, so each option is
// seen at its real size.
export function HeroShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-dashed border-cs-line-strong bg-cs-bg">
      <div className="cs-container grid items-center gap-12 pb-16 pt-12 md:pb-20 md:pt-16 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          <span className="inline-flex min-h-6 items-center gap-2 text-[0.8125rem] text-cs-ink-2">
            <span className="cs-data rounded-[var(--cs-radius-sm)] bg-cs-accent-soft px-1.5 py-0.5 text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-cs-accent">
              New
            </span>
            CommuteScout Drive for iPhone and Android
            <ArrowRight aria-hidden className="size-3.5" />
          </span>
          <p className="cs-display mt-6">
            Live road conditions, straight from the source.
          </p>
          <p className="cs-lede mt-6 max-w-[32rem]">
            Incidents, closures, chain controls, cameras and wildfires from 53 official sources across 37
            states, on one live map.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <span className="inline-flex h-11 items-center rounded-[var(--cs-radius-md)] bg-cs-accent px-5 text-[0.9375rem] font-medium text-cs-accent-ink shadow-[var(--cs-shadow-sm)]">
              Open the live map
            </span>
            <span className="inline-flex h-11 items-center rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface px-5 text-[0.9375rem] font-medium text-cs-ink shadow-[var(--cs-shadow-sm)]">
              Get the app
            </span>
          </div>
          <p className="mt-6 text-sm text-cs-ink-3">Free, with no account needed.</p>
        </div>
        <div className="min-w-0 lg:col-span-7 lg:pl-6">{children}</div>
      </div>
    </div>
  );
}

/** The frame every hero visual sits in, matching today's figure frame. */
export function HeroFrame({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <figure className={`rounded-[calc(var(--cs-radius-lg)+6px)] border border-cs-line bg-cs-surface-2 p-1.5 sm:p-2 ${className}`}>
      <div className="overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-line-strong bg-cs-surface shadow-[var(--cs-shadow-md)]">
        {children}
      </div>
    </figure>
  );
}
