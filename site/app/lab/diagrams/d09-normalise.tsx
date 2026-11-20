import { FigureFrame } from "@/components/figures/frame";

// 9. Before and after normalisation. Two real feed shapes, trimmed: a regional portal's XML
// lane closure (states._parse_nec_bundle: micro-degree coordinates, laneDetails with a
// status per lane) and a WZDx GeoJSON work zone (states._parse_ia_wzdx: [lon, lat] order,
// vehicle_impact). Both become the same marker dict the map, the API and MCP all read.
// Values are made up and generic.

function M({ n, k, children }: { n: number; k: string; children: React.ReactNode }) {
  return (
    <mark data-n={n} data-k={k}>
      {children}
    </mark>
  );
}

export default function D09Normalise() {
  return (
    <FigureFrame
      n={9}
      title="Two formats in, one format out"
      hint="Numbers mark where each field comes from"
      readout='kind: "lane_closure"'
      caption={
        <>
          Every agency describes a closure its own way. One sends coordinates as whole millionths of a degree and lists
          each lane; another sends longitude first and one word for the impact. CommuteScout translates each into the
          same fields, so the map, the REST API and the MCP server read every state the same way.
        </>
      }
    >
      <div className="dgf">
        <div className="dg-nz">
          <div>
            <pre className="dg-code">
              <span className="lbl">Regional portal · XML</span>
              {`<laneClosure>
  <desc>Right lane closed for paving</desc>
  <startLocation>
    <roadway>`}<M n={4} k="neutral">Highway A</M>{`</roadway>
    <lat>`}<M n={1} k="accent">44512345</M>{`</lat>
    <lon>`}<M n={1} k="accent">-71904210</M>{`</lon>
  </startLocation>
  `}<M n={2} k="closure">{`<laneDetails status="Cleared" …/>
  <laneDetails status="Blocked" …/>`}</M>{`
</laneClosure>`}
            </pre>
            <pre className="dg-code">
              <span className="lbl">State work-zone feed · WZDx GeoJSON</span>
              {`{ "geometry": { "type": "LineString",
    "coordinates": [`}<M n={1} k="accent">[-93.6021, 41.9874]</M>{`, …] },
  "properties": {
    "core_details": {
      "road_names": [`}<M n={4} k="neutral">&quot;Highway B&quot;</M>{`],
      "description": "Lane shift near Exit 14" },
    "vehicle_impact": `}<M n={2} k="closure">&quot;some-lanes-closed&quot;</M>{`,
    "event_status": `}<M n={3} k="ok">&quot;active&quot;</M>{` } }`}
            </pre>
          </div>
          <div>
            <p className="dg-arrow">Translate →</p>
            <ol className="dg-steps">
              <li data-k="accent">
                <span>1</span>
                <div>Coordinates: divide by 1,000,000, or swap [lon, lat] to lat, lon</div>
              </li>
              <li data-k="closure">
                <span>2</span>
                <div>Impact: 1 of 2 lanes blocked, or &ldquo;some-lanes-closed&rdquo;, both become <code>lane</code></div>
              </li>
              <li data-k="ok">
                <span>3</span>
                <div>Only what is in place now: planned and finished work is left out</div>
              </li>
              <li data-k="neutral">
                <span>4</span>
                <div>Road name kept; the agency is stamped as <code>src</code></div>
              </li>
            </ol>
          </div>
          <div>
            <pre className="dg-code out">
              <span className="lbl">CommuteScout marker · same for both</span>
              {`{
  "kind": "lane_closure",
  "lat": `}<M n={1} k="accent">44.512345</M>{`,
  "lon": `}<M n={1} k="accent">-71.90421</M>{`,
  "cls": `}<M n={2} k="closure">&quot;lane&quot;</M>{`,
  "label": "Right lane closed for paving",
  "route": `}<M n={4} k="neutral">&quot;Highway A&quot;</M>{`,
  "src": `}<M n={4} k="neutral">&quot;State DOT&quot;</M>{`,
  "dir": null,
  "since": null, "until": null,
  "lane_layout": { … },
  "path": [[44.51235, -71.90421], …]
}`}
            </pre>
          </div>
        </div>
      </div>
    </FigureFrame>
  );
}
