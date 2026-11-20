import { US_NATION, US_STATES, US_VIEWBOX } from "@/components/figures/us-map.geo";
import { LiveHero } from "./live-hero";

// Server half of the home hero's map: the state outlines as one static
// path, in the page's HTML, so the frame paints at full size before any
// script runs and nothing shifts when the live dots arrive.
const OUTLINES = US_STATES.map((s) => s.d).join("");

export function HeroMap() {
  return (
    <LiveHero
      base={
        <svg viewBox={US_VIEWBOX} aria-hidden className="absolute inset-0 h-full w-full">
          <path d={US_NATION} fill="var(--cs-surface-2)" />
          <path d={OUTLINES} fill="var(--cs-surface)" stroke="var(--cs-line-strong)" strokeWidth={0.7} strokeLinejoin="round" />
        </svg>
      }
    />
  );
}
