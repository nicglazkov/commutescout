"use client";

import { useId, useState } from "react";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { CodeBlock } from "./code-block";

// The REST API quickstart lives in the page head of /developers: three
// steps in the text column (QuickstartSteps) and, beside them, the request
// those steps refer to and what it returns (Quickstart). One request, one
// response, shown once.
//
// The request asks get_traffic at the account's saved Home (place=home
// resolves through the key's saved places, src/ca_roads_mcp/planning.py
// point_from and resolve), so the only thing to fill in is the key. A key
// pasted into the field only rewrites the command on this page; it is
// never stored or sent anywhere.
//
// The response follows get_traffic's payload (src/ca_roads_mcp/planning.py):
// readings (point, current_mph, freeflow_mph, percent_of_freeflow,
// condition), source and data_as_of. 41 of 63 mph is 65 percent, which the
// code calls "slow" (above 55 and up to 85 percent). The point is a
// placeholder, not a real place.

const RESPONSE = `{
  "readings": [
    {
      "point": "LAT,LON",
      "current_mph": 41,
      "freeflow_mph": 63,
      "percent_of_freeflow": 65,
      "condition": "slow"
    }
  ],
  "source": "TomTom traffic flow (nearest road segment to each point)",
  "data_as_of": "2026-11-19T17:42:08+00:00"
}`;

export function QuickstartSteps({ docsHref }: { docsHref: string }) {
  return (
    <section id="quickstart" className="dx-qs" aria-labelledby="quickstart-h">
      <div className="dx-qs-head">
        <h2 id="quickstart-h">Quickstart</h2>
        <a href={docsHref} className="dx-textlink">
          OpenAPI reference <ArrowUpRight aria-hidden="true" />
        </a>
      </div>
      <ol className="dx-qs-steps">
      <li>
        <span className="dx-qs-n" aria-hidden="true">1</span>
        <div>
          <h3>Get a free key</h3>
          <p>On the live map, choose Settings, sign in and create a key. It is shown once, so copy it.</p>
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
          <h3>Send the request</h3>
          <p>
            Live traffic at your saved Home. Swap <code className="dx-ic">home</code> for any saved place or
            an address.
          </p>
        </div>
      </li>
      <li>
        <span className="dx-qs-n" aria-hidden="true">3</span>
        <div>
          <h3>Read the response</h3>
          <p>Speed now against free flow, where the reading came from, and the time the data is as of.</p>
        </div>
      </li>
      </ol>
    </section>
  );
}

export function Quickstart({ apiRoot }: { apiRoot: string }) {
  const [key, setKey] = useState("");
  const inputId = useId();
  const noteId = useId();
  const shown = key.trim() || "YOUR_KEY";
  const command = `curl "${apiRoot}/tools/get_traffic?place=home" \\\n  -H "X-API-Key: ${shown}"`;

  return (
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
      <CodeBlock code={RESPONSE} lang="json" title="3 · 200 OK, sample response" copy={false} className="dx-qs-resp" />
    </div>
  );
}
