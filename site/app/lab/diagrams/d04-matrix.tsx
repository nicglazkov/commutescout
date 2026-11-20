import { FigureFrame } from "@/components/figures/frame";
import { STATE_COVERAGE, type StateRow } from "@/lib/state-coverage";

// 4. Source-type matrix. Which kind of publisher supplies each kind of data, and how often
// CommuteScout re-reads it (the feeds' cache times). State counts are counted from
// lib/state-coverage.ts, the same table the page shows below.

const yes = (key: keyof StateRow) => STATE_COVERAGE.filter((r) => r[key].startsWith("Y")).length;

const COLS = [
  { id: "state", label: "State agency's own feed" },
  { id: "wzdx", label: "Work-zone standard (WZDx)" },
  { id: "portal", label: "Shared regional portal" },
  { id: "national", label: "National service" },
  { id: "traffic", label: "Traffic data provider" },
] as const;
type Col = (typeof COLS)[number]["id"];

const ROWS: { kind: string; k: string; cells: Partial<Record<Col, string>>; states: string }[] = [
  { kind: "Crashes and incidents", k: "incident", cells: { state: "1–3 min", portal: "3 min" }, states: String(yes("incidents")) },
  { kind: "Closures and roadwork", k: "closure", cells: { state: "3–5 min", wzdx: "10 min", portal: "3 min" }, states: String(yes("closures")) },
  { kind: "Chain controls", k: "chain", cells: { state: "3–5 min" }, states: String(yes("chains")) },
  { kind: "Message signs", k: "neutral", cells: { state: "2.5–3 min", portal: "3 min" }, states: String(yes("signs")) },
  { kind: "Road weather stations", k: "weather", cells: { state: "2.5–3 min", portal: "3 min" }, states: String(yes("weather")) },
  { kind: "Camera lists", k: "neutral", cells: { state: "2.5–3 min", portal: "10 min" }, states: String(yes("cameras")) },
  { kind: "Wildfires", k: "fire", cells: { state: "5 min", national: "5 min" }, states: "all" },
  { kind: "Weather alerts", k: "weather", cells: { national: "5 min" }, states: "all" },
  { kind: "Earthquakes", k: "neutral", cells: { national: "5 min" }, states: "all" },
  { kind: "Traffic speed", k: "accent", cells: { traffic: "60 s" }, states: "all" },
];

export default function D04Matrix() {
  return (
    <FigureFrame
      n={4}
      title="Who publishes what"
      hint="Filled cell: that kind of publisher supplies it. Text: how often we re-read it"
      readout={`${STATE_COVERAGE.length} states with their own feeds`}
      caption={
        <>
          Road data comes from four kinds of publisher. Most of it is a state agency&apos;s own feed; some states only
          publish roadwork in the national work-zone standard, three share one regional portal, and a few kinds of data
          come from a national service for every state. Each one is translated into the same marker format before it
          reaches the map.
        </>
      }
    >
      <div className="dgf" style={{ overflowX: "auto" }}>
        <table className="dg-mx">
          <thead>
            <tr>
              <th scope="col">
                <span className="csf-sr">Kind of data</span>
              </th>
              {COLS.map((c) => (
                <th key={c.id} scope="col">
                  {c.label}
                </th>
              ))}
              <th scope="col" style={{ textAlign: "right" }}>
                States
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.kind} data-k={r.k}>
                <th scope="row" className="row">
                  <span aria-hidden="true" />
                  {r.kind}
                </th>
                {COLS.map((c) => (
                  <td key={c.id} data-on={r.cells[c.id] ? "" : undefined}>
                    {r.cells[c.id] ?? <span className="csf-sr">no</span>}
                  </td>
                ))}
                <td className="states">{r.states}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </FigureFrame>
  );
}
