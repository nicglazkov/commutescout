"use client";

import { useState } from "react";
import { PointerHint, FigureFrame } from "./frame";

// plan_trip, drawn literally as a strip map. Everything here mirrors the tool's output
// (src/ca_roads_mcp/planning.py plan_trip, :692-879; MCP wrapper src/ca_roads_mcp/server.py:1769-1809):
// - every live item is snapped onto the route line (locate_on_line) and given `mile`, rounded to 0.1
//   (event_view(m, along * MILES_PER_METER), planning.py:788-817), sorted by distance along the route
// - sections in `on_route`: incidents, closures, chain_controls, message_signs, cameras, road_weather, tolls,
//   speed_and_red_light_cameras, wildfires_nearby (SECTION / NEAR_M / CAPS, planning.py:59-69); a wildfire
//   counts if it is within 16 km of the line
// - `traffic`: minutes_with_traffic, typical_minutes_for_this_departure, minutes_no_traffic (planning.py:828-837)
// - `weather`: NWS alerts sampled along the line and the forecast at the destination for the arrival hour (:846-855)
// - `summary` is built by _trip_summary (planning.py:896-925); its "on the route right now" counts closures,
//   incidents, chain controls and wildfires nearby only.
// Sample values are illustrative and location-agnostic.

type Kind = "incident" | "closure" | "chain" | "fire" | "weather" | "sign" | "camera" | "toll";
type Item = { mile: number; kind: Kind; section: string; text: string };
const TOTAL = 46.8;
// A winter mountain drive, in an order that happens: a crash in town, the signs warn of chains,
// a lane closed for plowing, the chain-up area and its camera, the road weather station at the pass,
// then the drop to a friend's place on the far side. No wildfire, no roadwork: wrong season.
const ITEMS: Item[] = [
  { mile: 6.2, kind: "toll", section: "tolls", text: "Toll plaza, $3.50" },
  { mile: 12.4, kind: "incident", section: "incidents", text: "Crash, right lane blocked" },
  { mile: 18.7, kind: "sign", section: "message_signs", text: "Sign reads: CHAINS REQUIRED 12 MI AHEAD" },
  { mile: 24.6, kind: "closure", section: "closures", text: "Right lane closed for snow plowing" },
  { mile: 28.9, kind: "camera", section: "cameras", text: "Camera at Exit 29: snow on the road, image a minute old" },
  { mile: 31.0, kind: "chain", section: "chain_controls", text: "Chains required, except 4WD with snow tires" },
  { mile: 36.4, kind: "weather", section: "road_weather", text: "Station at the pass: pavement 27°F, light snow" },
];
const KIND_LABEL: Record<Kind, string> = {
  incident: "Incident",
  closure: "Closure",
  chain: "Chain control",
  fire: "Wildfire nearby",
  weather: "Road weather",
  sign: "Message sign",
  camera: "Camera",
  toll: "Toll",
};
const DRIVE = { traffic: 64, typical: 58, free: 53 };

const X0 = 56;
const X1 = 944;
const LINE_Y = 104;
const xOf = (mile: number) => X0 + (mile / TOTAL) * (X1 - X0);
// A pin's mile label sits to the right of its head unless the next pin's stem is close enough
// for the label to run into it (it did at mile 28.9, one stem before the chain control); then
// it sits on the left, where there is room.
const LABEL_ROOM = 52;
const labelLeft = (i: number) => {
  const x = xOf(ITEMS[i].mile);
  const next = ITEMS[i + 1] ? xOf(ITEMS[i + 1].mile) - x : Infinity;
  const prev = i > 0 ? x - xOf(ITEMS[i - 1].mile) : Infinity;
  return next < LABEL_ROOM && prev >= LABEL_ROOM;
};

export default function RouteStrip({ n = 4 }: { n?: number | string }) {
  const [hot, setHot] = useState<number | null>(null);
  const it = hot !== null ? ITEMS[hot] : null;
  const maxMin = 70;

  return (
    <FigureFrame
      n={n}
      title="One plan_trip answer"
      className="csf-route"
      hint={<PointerHint fine="Hover or focus an item to find it on the strip" coarse="Tap an item to find it on the strip" />}
      readout={it ? `mile ${it.mile.toFixed(1)} · ${KIND_LABEL[it.kind].toLowerCase()}` : `${TOTAL} mi · ${ITEMS.length} live items on the line`}
      caption={
        <>
          Every live report on the route gets a <b>mile</b> from the start, so the answer reads in driving order. It also has
          three drive times and the forecast for when you arrive. A sample winter trip.
        </>
      }
    >
      <div className="rs">
        <div className="rs-head">
          <p className="rs-summary">
            <span className="rs-key csf-mono">summary</span>
            Home to a friend&apos;s place: {TOTAL} mi via Interstate; about 1 h 4 min leaving 7:30 AM, arriving around 8:34 AM; 11 min of that is
            traffic; on the route right now: 1 closure, 1 incident, 1 chain control.
          </p>
          <dl className="rs-times" aria-label="Drive time for this departure">
            {(
              [
                ["With traffic", DRIVE.traffic, "minutes_with_traffic"],
                ["Typical", DRIVE.typical, "typical_minutes_for_this_departure"],
                ["Free-flow", DRIVE.free, "minutes_no_traffic"],
              ] as const
            ).map(([label, v, key], i) => (
              <div key={key} className="rs-time" data-first={i === 0 ? "" : undefined}>
                <dt>{label}</dt>
                <dd>
                  <span className="rs-track">
                    <span className="rs-bar" style={{ width: `${(v / maxMin) * 100}%` }} />
                  </span>
                  <span className="csf-mono">{v} min</span>
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <svg className="csf-svg rs-strip csf-desk" viewBox="0 0 1000 150" role="img" aria-label={`Strip map of a ${TOTAL}-mile route from Home to a friend's place with ${ITEMS.length} live items pinned at their mile.`}>
          {/* mileposts */}
          {Array.from({ length: Math.floor(TOTAL) + 1 }, (_, m) => m).map((m) => (
            <line key={m} x1={xOf(m)} x2={xOf(m)} y1={LINE_Y + 10} y2={LINE_Y + (m % 5 === 0 ? 18 : 14)} className={m % 5 === 0 ? "rs-tick-major" : "rs-tick"} />
          ))}
          {Array.from({ length: Math.floor(TOTAL / 10) + 1 }, (_, i) => i * 10).map((m) => (
            <text key={m} x={xOf(m)} y={LINE_Y + 32} textAnchor="middle" className="rs-mile">
              {m === 0 ? "mile 0" : m}
            </text>
          ))}
          <text x={xOf(TOTAL)} y={LINE_Y + 32} textAnchor="middle" className="rs-mile rs-mile-end">
            {TOTAL}
          </text>
          {/* the route */}
          <line x1={X0} x2={X1} y1={LINE_Y} y2={LINE_Y} className="rs-road-o" />
          <line x1={X0} x2={X1} y1={LINE_Y} y2={LINE_Y} className="rs-road" />
          {/* pins, alternating heights so neighbours never collide */}
          {ITEMS.map((item, i) => {
            const x = xOf(item.mile);
            const y = i % 2 ? 30 : 58;
            return (
              <g
                key={item.mile}
                className="rs-pin"
                data-kind={item.kind}
                data-hot={hot === i ? "" : undefined}
                data-dim={hot !== null && hot !== i ? "" : undefined}
                onPointerEnter={() => setHot(i)}
                onPointerLeave={(e) => { if (e.pointerType === "mouse") setHot(null); }}
              >
                <line x1={x} x2={x} y1={y + 11} y2={LINE_Y - 4} className="rs-stem" />
                <circle cx={x} cy={LINE_Y} r={4} className="rs-foot" />
                <circle cx={x} cy={y} r={11} className="rs-head-dot" />
                <text x={x} y={y + 4} textAnchor="middle" className="rs-num">
                  {i + 1}
                </text>
                <text x={labelLeft(i) ? x - 16 : x + 16} y={y + 4} textAnchor={labelLeft(i) ? "end" : "start"} className="rs-pin-mile">
                  {item.mile.toFixed(1)}
                </text>
              </g>
            );
          })}
          {/* ends */}
          <g className="rs-end">
            <circle cx={X0} cy={LINE_Y} r={7} />
            <text x={X0} y={LINE_Y - 16} textAnchor="middle">
              Home
            </text>
          </g>
          <g className="rs-end">
            <rect x={X1 - 7} y={LINE_Y - 7} width={14} height={14} rx={3} />
            <text x={X1} y={LINE_Y - 16} textAnchor="middle">
              Friend&apos;s place
            </text>
          </g>
        </svg>

        <ol className="rs-list" aria-label="On the route, in driving order">
          <li className="rs-row rs-row-end rs-row-home">
            <span className="rs-row-num rs-row-num-end rs-row-num-home" aria-hidden="true" />
            <span className="rs-row-mile csf-mono">0.0</span>
            <span className="rs-row-body">
              <span className="rs-row-kind">Home</span>
              <span className="rs-row-text">Leaving 7:30 AM</span>
            </span>
          </li>
          {ITEMS.map((item, i) => (
            <li
              key={item.mile}
              tabIndex={0}
              className="rs-row csf-focus"
              data-kind={item.kind}
              data-hot={hot === i ? "" : undefined}
              onPointerEnter={() => setHot(i)}
              onPointerLeave={(e) => { if (e.pointerType === "mouse") setHot(null); }}
              onFocus={() => setHot(i)}
              onBlur={() => setHot(null)}
            >
              <span className="rs-row-num" aria-hidden="true">
                {i + 1}
              </span>
              <span className="rs-row-mile csf-mono">
                <span className="csf-sr">mile </span>
                {item.mile.toFixed(1)}
              </span>
              <span className="rs-row-body">
                <span className="rs-row-kind">{KIND_LABEL[item.kind]}</span>
                <span className="rs-row-text">{item.text}</span>
              </span>
            </li>
          ))}
          <li className="rs-row rs-row-end" aria-label={`Friend's place at mile ${TOTAL}`}>
            <span className="rs-row-num rs-row-num-end" aria-hidden="true" />
            <span className="rs-row-mile csf-mono">{TOTAL}</span>
            <span className="rs-row-body">
              <span className="rs-row-kind">Friend&apos;s place</span>
              <span className="rs-row-text">Forecast on arrival: snow showers, 30°F. Alert along the route: winter storm warning.</span>
            </span>
          </li>
        </ol>
      </div>
    </FigureFrame>
  );
}
