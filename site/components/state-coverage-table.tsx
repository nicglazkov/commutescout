import { Check, Minus } from "lucide-react";
import type { StateRow } from "@/lib/state-coverage";

// Page-owned component for site/app/data-sources/page.tsx: the per-state
// coverage matrix from docs/state-coverage.md, restyled from a 38-row
// markdown table into a scrollable data grid. Plain server component, no
// "use client": sticky positioning and overflow scrolling are CSS-only.
//
// The container scrolls both axes (overflow-auto with a min-width table
// wider than a phone screen forces horizontal scroll on mobile; a
// max-height forces vertical scroll instead of pushing the rest of the
// page down 37 rows). The header row and the state-name column both stay
// pinned (position: sticky) while the reader scrolls, so a cell is never
// seen without knowing its row and column.

const COLUMNS: { key: keyof StateRow; label: string }[] = [
  { key: "incidents", label: "Incidents" },
  { key: "closures", label: "Closures" },
  { key: "cameras", label: "Cameras" },
  { key: "signs", label: "Signs" },
  { key: "weather", label: "Road weather" },
  { key: "chains", label: "Chains" },
  { key: "wildfires", label: "Wildfires" },
];

function CoverageCell({ value }: { value: string }) {
  if (value === "n/a") {
    return <span className="text-cs-ink/40">n/a</span>;
  }
  if (value.startsWith("Y")) {
    const suffix = value.slice(1).trim(); // "", "*", "**", "(wz)", "(passes)"
    return (
      <span className="inline-flex items-center gap-1">
        <Check className="text-cs-sky size-4 shrink-0" aria-hidden="true" />
        {suffix && <span className="text-cs-ink/50 text-xs">{suffix}</span>}
      </span>
    );
  }
  // "- (n)": the state's public feeds do not offer this keylessly. The
  // footnote number links to its reason in the "Why the gaps" list below
  // the table.
  const n = value.match(/\((\d+)\)/)?.[1];
  return (
    <span className="inline-flex items-center gap-1">
      <Minus className="text-cs-ink/30 size-4 shrink-0" aria-hidden="true" />
      {n && (
        <a
          href={`#gap-${n}`}
          className="text-cs-ink/40 hover:text-cs-sky text-xs underline-offset-2 hover:underline"
        >
          {n}
        </a>
      )}
    </span>
  );
}

export function StateCoverageTable({ rows }: { rows: StateRow[] }) {
  return (
    <div className="ring-cs-line max-h-[34rem] overflow-auto rounded-xl ring-1">
      <table className="w-full min-w-[880px] border-collapse text-left text-sm">
        <thead>
          <tr>
            <th className="bg-cs-paper text-cs-ink sticky left-0 top-0 z-20 border-b border-cs-line px-4 py-3 font-medium">
              State
            </th>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className="bg-cs-paper text-cs-ink sticky top-0 z-10 border-b border-cs-line px-4 py-3 font-medium whitespace-nowrap"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.state} className="even:bg-cs-bg/40">
              <th
                scope="row"
                className="bg-cs-paper text-cs-ink sticky left-0 z-10 border-b border-cs-line px-4 py-2.5 text-left font-medium whitespace-nowrap"
              >
                {row.state}
              </th>
              {COLUMNS.map((col) => (
                <td key={col.key} className="border-b border-cs-line px-4 py-2.5">
                  <CoverageCell value={row[col.key]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
