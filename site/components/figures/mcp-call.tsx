"use client";

import { useEffect, useRef } from "react";
import { FigureFrame } from "./frame";
import { useInView, useReducedMotion } from "./hooks";

// One MCP tool call, end to end, as a calm loop with no controls (owner review: "a clear,
// animated, cool, pretty thing, nothing else").
// - the assistant sends a JSON-RPC 2.0 `tools/call` for plan_trip to the stateless streamable HTTP
//   endpoint /mcp (src/ca_roads_mcp/server.py streamable_http_path, stateless_http)
// - plan_trip (src/ca_roads_mcp/planning.py) resolves saved places, routes the departure with traffic,
//   pins live reports to the line, reads the arrival forecast and writes `summary`
// - the result comes back as structuredContent; the server instructions tell the assistant to lead
//   with `summary`.
// The sample is the same winter trip as the route strip figure.
//
// Parts carry data-step. A loop sets data-on on every part whose step has come, then clears them.
// Server render, no JS and reduced motion: the root keeps data-static and shows the finished call.

const TIMES = [300, 1200, 2300, 2900, 3400, 3900, 4200, 4500, 4800, 5400, 6100, 6700, 7900];
const LOOP = 14500;
const HOLD = 13400;

const STEPS = ["Look up Home and the destination", "Route the 7:30 AM drive with traffic", "Pin live reports to the route", "Read the forecast on arrival", "Write the summary"];
const STEP_AT = [3, 4, 6, 10, 11];
const SOURCES: [string, string, number][] = [
  ["traffic", "Traffic speeds", 5],
  ["incident", "Crashes and incidents", 7],
  ["closure", "Closures", 8],
  ["chain", "Chain controls", 9],
  ["weather", "Weather forecast", 10],
];

export default function McpCall({ n = 7 }: { n?: number | string }) {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const inView = useInView(root, "0px 0px -10% 0px");

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (reduced || !inView) {
      el.setAttribute("data-static", "");
      return;
    }
    const parts = Array.from(el.querySelectorAll<HTMLElement>("[data-step]"));
    const timers: number[] = [];
    const show = (k: number) => {
      for (const p of parts) {
        if (Number(p.dataset.step) === k) p.setAttribute("data-on", "");
        if (p.dataset.offAt && Number(p.dataset.offAt) === k) p.setAttribute("data-off", "");
      }
    };
    const clear = () => parts.forEach((p) => (p.removeAttribute("data-on"), p.removeAttribute("data-off")));
    const run = () => {
      clear();
      TIMES.forEach((t, i) => timers.push(window.setTimeout(() => show(i + 1), t)));
      timers.push(window.setTimeout(clear, HOLD));
      timers.push(window.setTimeout(run, LOOP));
    };
    el.removeAttribute("data-static");
    run();
    return () => {
      timers.forEach(clearTimeout);
      el.setAttribute("data-static", "");
      clear();
    };
  }, [reduced, inView]);

  return (
    <FigureFrame
      n={n}
      title="One question, one tool call"
      className="csf-mcp"
      caption={
        <>
          Your assistant turns the question into one <code>plan_trip</code> call. CommuteScout reads the live sources and sends back
          the data with a plain-language <code>summary</code>, which the assistant answers from.
        </>
      }
    >
      <div ref={root} className="mx" data-static="">
        <div className="mx-panel mx-chat">
          <div className="mx-panel-head">
            <span className="mx-dot3" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <b>Assistant</b>
          </div>
          <p className="mx-bubble mx-q" data-step={1}>
            How&apos;s the drive from home to my friend&apos;s place if I leave at 7:30?
          </p>
          <span className="mx-typing" data-step={12} data-off-at={13} aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <p className="mx-bubble mx-a" data-step={13}>
            About 1 h 4 min, 11 of it traffic. A crash at mile 12, a lane closed for plowing at 25, and chains required from mile
            31. Snow showers when you arrive.
            <small>from summary</small>
          </p>
        </div>

        <div className="mx-link" aria-hidden="true">
          <span className="mx-track" />
          <span className="mx-pill" data-step={2}>
            tools/call
          </span>
          <span className="mx-runner" data-step={2} />
          <span className="mx-pill" data-dir="back" data-step={12}>
            result
          </span>
          <span className="mx-runner" data-dir="back" data-step={12} />
        </div>

        <div className="mx-panel mx-server">
          <div className="mx-panel-head">
            <b>CommuteScout</b>
            <span className="mx-mono">MCP</span>
          </div>
          <span className="mx-tool">plan_trip</span>
          <ol className="mx-steps" aria-label="What the tool does">
            {STEPS.map((s, i) => (
              <li key={s} data-step={STEP_AT[i]}>
                <span className="mx-tick" aria-hidden="true" />
                {s}
              </li>
            ))}
          </ol>
        </div>

        <div className="mx-link" data-w="s" aria-hidden="true">
          <span className="mx-track" />
          <span className="mx-runner" data-step={4} />
        </div>

        <div className="mx-panel mx-feeds">
          <div className="mx-panel-head">
            <b>Live sources</b>
          </div>
          <ul className="mx-sources">
            {SOURCES.map(([k, label, step]) => (
              <li key={k} className="mx-src" data-k={k} data-step={step}>
                <i aria-hidden="true" />
                {label}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </FigureFrame>
  );
}
