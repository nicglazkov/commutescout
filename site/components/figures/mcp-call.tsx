"use client";

import { useEffect, useRef, useState } from "react";
import { FigureFrame } from "./frame";
import { useInView, useReducedMotion } from "./hooks";

// One MCP tool call, end to end, as the server speaks it:
// - Streamable HTTP, stateless, at /mcp (src/ca_roads_mcp/server.py:2067-2071: streamable_http_path="/mcp",
//   stateless_http=True); host mcp.commutescout.com
// - the assistant sends JSON-RPC 2.0 `tools/call` with the tool name and arguments; plan_trip is
//   @mcp.tool at src/ca_roads_mcp/server.py:1769-1809 (origin, destination, depart_at ...)
// - a key is optional (Authorization: Bearer cs_live_... or X-API-Key, ApiKeyMiddleware in
//   src/ca_roads_mcp/ratelimit.py); without one the call is keyless and limited per address
// - the tool returns a dict: FastMCP sends it as structuredContent plus the same JSON as a text block;
//   `summary` is a field of that dict (_trip_summary, src/ca_roads_mcp/planning.py:896-925)
// - the server instructions tell the assistant to lead with `summary` and relay notes and stale data_as_of.

type Step = 0 | 1 | 2 | 3 | 4;
const STEPS = [
  { n: 1, title: "You ask", who: "Assistant" },
  { n: 2, title: "tools/call", who: "JSON-RPC over HTTPS" },
  { n: 3, title: "plan_trip runs", who: "CommuteScout" },
  { n: 4, title: "Result back", who: "structuredContent" },
] as const;

const REQUEST = `{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "plan_trip",
    "arguments": {
      "origin": "home",
      "destination": "cabin",
      "depart_at": "7:30am"
    }
  }
}`;

const RESULT = `{
  "jsonrpc": "2.0",
  "id": 7,
  "result": {
    "structuredContent": {
      "summary": "Home to Cabin:
        46.8 mi; about 1 h 4 min
        leaving 7:30 AM ...",
      "traffic": {
        "minutes_with_traffic": 64
      },
      "on_route": {
        "incidents": [
          { "mile": 12.4, ... }
        ], ...
      }
    },
    "content": [{ "type": "text" }]
  }
}`;

const WORK = ["Look up Home and Cabin, your saved places", "Route the drive, with traffic for 7:30 AM", "Pin live items to the line by mile", "Weather along the way and on arrival", "Write the summary"];

export default function McpCall({ n = 7 }: { n?: number | string }) {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const inView = useInView(root);
  const [step, setStep] = useState<Step>(0);
  const played = useRef(false);
  useEffect(() => {
    if (!inView || reduced || played.current) return;
    played.current = true;
    const seq: Step[] = [1, 2, 3, 4, 0];
    const timers = seq.map((s, i) => window.setTimeout(() => setStep(s), 300 + i * 2200));
    return () => timers.forEach(clearTimeout);
  }, [inView, reduced]);
  const on = (k: number) => step === 0 || step === k;

  return (
    <FigureFrame
      n={n}
      title="One question, one tool call"
      className="csf-mcp"
      hint="Step through the call"
      readout={step === 0 ? "1 request · 1 tool · 1 result" : `Step ${step} of 4 · ${STEPS[step - 1].title}`}
      controls={
        <div className="csf-controls" role="group" aria-label="Show a step">
          {([0, 1, 2, 3, 4] as Step[]).map((s) => (
            <button key={s} type="button" className="csf-chip" aria-pressed={step === s} onClick={() => setStep(s)}>
              {s === 0 ? "Whole call" : `${s}. ${STEPS[s - 1].title}`}
            </button>
          ))}
        </div>
      }
      caption={
        <>
          An assistant connected to the CommuteScout MCP server turns your question into one <code>tools/call</code> request. The
          server runs the tool and returns structured data with a plain-language <code>summary</code> inside it, which the
          assistant is told to lead with. A key is optional: it only lets the tools read your saved places, like Home or Cabin.
        </>
      }
    >
      <div ref={root} className="mc" data-step={step}>
        <ol className="mc-lane">
          <li className="mc-panel mc-chat" data-on={on(1) || on(4) ? "" : undefined}>
            <div className="mc-head">
              <span className="mc-n">1</span>
              <b>Assistant</b>
            </div>
            <div className="mc-bubble mc-user">How&apos;s the drive from home to the cabin if I leave at 7:30?</div>
            <div className="mc-bubble mc-bot" data-on={on(4) ? "" : undefined}>
              About 1 h 4 min, 11 of it traffic. One crash at mile 12, a lane closed at 24, and chains required from mile 31.
              Snow showers on arrival.
              <span className="mc-cite">from summary</span>
            </div>
          </li>
          <li className="mc-panel mc-code" data-on={on(2) ? "" : undefined}>
            <div className="mc-head">
              <span className="mc-n">2</span>
              <b>tools/call</b>
              <span className="mc-tag csf-mono">POST /mcp</span>
            </div>
            <pre className="csf-mono" aria-label="JSON-RPC request">{REQUEST}</pre>
          </li>
          <li className="mc-panel mc-tool" data-on={on(3) ? "" : undefined}>
            <div className="mc-head">
              <span className="mc-n">3</span>
              <b>plan_trip</b>
              <span className="mc-tag csf-mono">CommuteScout</span>
            </div>
            <ul className="mc-work">
              {WORK.map((w, i) => (
                <li key={w} style={{ ["--i" as string]: i }}>
                  <span className="mc-tick" aria-hidden="true" />
                  {w}
                </li>
              ))}
            </ul>
          </li>
          <li className="mc-panel mc-code" data-on={on(4) ? "" : undefined}>
            <div className="mc-head">
              <span className="mc-n">4</span>
              <b>Result</b>
              <span className="mc-tag csf-mono">structuredContent</span>
            </div>
            <pre className="csf-mono" aria-label="JSON-RPC result">{RESULT}</pre>
          </li>
        </ol>
      </div>
    </FigureFrame>
  );
}
