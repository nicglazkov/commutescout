"use client";

import { useId, useState } from "react";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { CodeBlock } from "./code-block";

// The REST API quickstart, shown as a band right under the page head so it
// is above the fold on a desktop: get a key, copy one request that works
// as-is, see what comes back. The request asks get_nearby_events around
// the account's saved Home (place=home resolves through the key's saved
// places, src/ca_roads_mcp/planning.py resolve), so the only thing to fill
// in is the key. A key pasted into the field only rewrites the command on
// this page; it is never stored or sent anywhere.
//
// The sample response follows get_nearby_events' payload
// (src/ca_roads_mcp/server.py): count, total_in_radius, filters, events
// nearest first, notes, data_as_of. Values are placeholders, not a record.

const SAMPLE = `{
  "count": 2,
  "total_in_radius": 2,
  "filters": { "center": "LAT,LON", "radius_km": 40,
               "kinds": ["chain", "closure", "fire", "incident"] },
  "events": [
    { "kind": "incident", "miles_away": 3.2, "type": "Crash",
      "summary": "Crash, right lane blocked", "route": "ROUTE",
      "lat": LAT, "lon": LON, "closure_class": null,
      "source": "State DOT" },
    { "kind": "lane_closure", "miles_away": 11.8, "type": "Roadwork",
      "summary": "Right lane closed for paving", "route": "ROUTE",
      "lat": LAT, "lon": LON, "closure_class": "lane",
      "source": "State DOT" }
  ],
  "notes": [],
  "data_as_of": "2026-11-19T16:00:00+00:00"
}`;

export function Quickstart({ apiRoot, docsHref }: { apiRoot: string; docsHref: string }) {
  const [key, setKey] = useState("");
  const inputId = useId();
  const noteId = useId();
  const shown = key.trim() || "YOUR_KEY";
  const command = `curl "${apiRoot}/tools/get_nearby_events?place=home" \\\n  -H "X-API-Key: ${shown}"`;

  return (
    <section id="quickstart" className="dx-qs" aria-labelledby="quickstart-h">
      <div className="dx-qs-inner">
        <div className="dx-qs-head">
          <h2 id="quickstart-h">Quickstart</h2>
          <p>Three steps, about a minute.</p>
          <a href={docsHref} className="dx-textlink dx-qs-ref">
            Browse the OpenAPI reference <ArrowUpRight aria-hidden="true" />
          </a>
        </div>

        <div className="dx-qs-grid">
          <ol className="dx-qs-steps">
            <li>
              <span className="dx-qs-n" aria-hidden="true">1</span>
              <div>
                <h3>Get a free key</h3>
                <p>On the live map, choose Settings, sign in, and create a key. It is shown once, so copy it.</p>
                <div className="dx-qs-act">
                  <a href="/map?settings=keys" className="dx-btn dx-btn-primary dx-qs-cta">
                    Get a free key <ArrowRight aria-hidden="true" />
                  </a>
                  <small>Free plan: 2,000 requests a day</small>
                </div>
              </div>
            </li>
            <li>
              <span className="dx-qs-n" aria-hidden="true">2</span>
              <div>
                <h3>Copy the request</h3>
                <p>
                  Live events within 40 km of your saved Home. Swap <code className="dx-ic">home</code> for any
                  saved place or address.
                </p>
              </div>
            </li>
            <li>
              <span className="dx-qs-n" aria-hidden="true">3</span>
              <div>
                <h3>See the response</h3>
                <p>Events nearest first, each naming its agency, plus the time the data is as of.</p>
              </div>
            </li>
          </ol>

          <div className="dx-qs-panels">
            <div className="dx-qs-req">
              <CodeBlock code={command} lang="bash" title="2 · Request" />
              <div className="dx-qs-key">
                <label htmlFor={inputId}>Paste your key to fill it in</label>
                <input
                  id={inputId}
                  type="text"
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  placeholder="YOUR_KEY"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  aria-describedby={noteId}
                />
                <p id={noteId}>Optional. It stays on this page.</p>
              </div>
            </div>
            <CodeBlock code={SAMPLE} lang="json" title="3 · 200 OK, sample response" className="dx-qs-resp" />
          </div>
        </div>
      </div>
    </section>
  );
}
