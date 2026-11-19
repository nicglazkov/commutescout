import { Check, Minus } from "lucide-react";
import type { StateRow } from "@/lib/state-coverage";

// Page-owned component for site/app/data-sources/page.tsx: the per-state
// coverage matrix from docs/state-coverage.md as a scrollable data grid.
// Plain server component; sticky positioning and overflow scrolling are
// CSS-only (components/docs/docs.css, .dx-matrix).
//
// The container scrolls both axes with a bounded height, so 37 rows do
// not push the rest of the page down. The header row and the state
// column stay pinned, so a cell is never seen without its row and column.

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
    return <span className="dx-matrix-na">n/a</span>;
  }
  if (value.startsWith("Y")) {
    const suffix = value.slice(1).trim(); // "", "*", "**", "(wz)", "(passes)"
    return (
      <span className="dx-matrix-yes">
        <Check aria-hidden="true" />
        <span className="sr-only">Live</span>
        {suffix && <span className="dx-matrix-suffix">{suffix}</span>}
      </span>
    );
  }
  // "- (n)": the state's public feeds do not offer this keylessly. The
  // footnote number links to its reason in the "Why the gaps" list.
  const n = value.match(/\((\d+)\)/)?.[1];
  return (
    <span className="dx-matrix-no">
      <Minus aria-hidden="true" />
      <span className="sr-only">Not available</span>
      {n && (
        <a href={`#gap-${n}`} aria-label={`Reason ${n}`}>
          {n}
        </a>
      )}
    </span>
  );
}

export function StateCoverageTable({ rows }: { rows: StateRow[] }) {
  return (
    <div className="dx-matrix" tabIndex={0} role="region" aria-label="Coverage by state, scrollable">
      <table>
        <caption className="sr-only">What each live state has on the map</caption>
        <thead>
          <tr>
            <th scope="col">State</th>
            {COLUMNS.map((col) => (
              <th key={col.key} scope="col">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.state}>
              <th scope="row">{row.state}</th>
              {COLUMNS.map((col) => (
                <td key={col.key}>
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
