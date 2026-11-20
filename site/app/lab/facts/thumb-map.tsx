import { STATE_COVERAGE } from "@/lib/state-coverage";
import { US_NATION, US_STATES, US_VIEWBOX } from "@/components/figures/us-map.geo";
import { depthOf } from "./facts-data";

// A small, unlabelled coverage map for header mockups: true state shapes
// (the same precomputed geometry as the About page's map), shaded by how
// many of the five live layers each covered state publishes. Decorative
// next to the numbers it summarises, so it is hidden from screen readers.
const DEPTH = new Map(STATE_COVERAGE.map((r) => [r.state, depthOf(r)]));

export function ThumbMap({ className }: { className?: string }) {
  return (
    <svg viewBox={US_VIEWBOX} className={"fx-thumbmap" + (className ? " " + className : "")} aria-hidden="true" focusable="false">
      <path d={US_NATION} className="fx-tm-nation" />
      {US_STATES.map((s) => {
        const d = DEPTH.get(s.name) ?? 0;
        return <path key={s.id} d={s.d} className="fx-tm-state" data-depth={d} />;
      })}
    </svg>
  );
}
