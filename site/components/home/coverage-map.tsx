import { US_NATION, US_STATES, US_VIEWBOX } from "@/components/figures/us-map.geo";
import { depth, depthFill } from "./coverage-data";
import { StateReadout } from "./state-readout";

// Server half of the home page's state map: every state shaded by how many
// kinds of road report its own agencies publish, rendered into the HTML.
// Paths carry no stroke of their own so the client's <use> outline of the
// chosen state can set one.
export function CoverageMap() {
  return (
    <StateReadout
      states={US_STATES.map((s) => ({ id: s.id, name: s.name }))}
      map={
        <svg viewBox={US_VIEWBOX} role="img" aria-label="Map of the US, each state shaded by how many kinds of road report its own agencies publish." className="block h-auto w-full">
          <path d={US_NATION} fill="var(--cs-surface-2)" />
          <g stroke="var(--cs-surface)" strokeWidth={0.9} strokeLinejoin="round">
            {US_STATES.map((s) => (
              <path key={s.id} id={`cov-${s.id}`} data-st={s.name} d={s.d} fill={depthFill(depth(s.name))}>
                <title>{s.name}</title>
              </path>
            ))}
          </g>
        </svg>
      }
    />
  );
}
