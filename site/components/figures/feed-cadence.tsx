"use client";

import { useState, type KeyboardEvent } from "react";
import { FigureFrame } from "./frame";

// One hour of refreshes. Each row is a feed family: how often its cache refetches (TTL) and the age at which
// the freshness monitor calls it stale. Sources:
// - refresh: incidents 60 s, closures / chain controls / wildfires 300 s (src/ca_roads/* feed TTLs),
//   message signs and road weather 150 s (portal.py:30 TTL_SECONDS), other states' 511 / WZDx events 180 s,
//   cameras 150 s
// - stale limits: src/ca_roads_demo/freshness.py:36-44 (CALIFORNIA: incidents 20 min, closures 30, chains 30,
//   wildfires 60, cameras 7 h, signs 30, road weather 60) and :50 (STATE_STALE_S, 90 min)
// - the monitor checks every 5 min (CHECK_EVERY_S, :28) and reports a source only after 2 failed checks
//   (GRACE_CHECKS, :33); a stale source keeps being served, flagged (module docstring)
// - the published live bundle is rebuilt every 30 s (src/ca_roads_demo/snapshot.py:63-72)

type Feed = { name: string; every: number; limit: number; tone: string };
const FEEDS: Feed[] = [
  { name: "Incident logs", every: 60, limit: 20, tone: "incident" },
  { name: "Closures and roadwork", every: 300, limit: 30, tone: "closure" },
  { name: "Chain controls", every: 300, limit: 30, tone: "chain" },
  { name: "Wildfires", every: 300, limit: 60, tone: "fire" },
  { name: "Message signs", every: 150, limit: 30, tone: "ink" },
  { name: "Road weather", every: 150, limit: 60, tone: "weather" },
  { name: "Other states' events", every: 180, limit: 90, tone: "ink" },
  { name: "Cameras", every: 150, limit: 420, tone: "ink" },
];
const fmtEvery = (s: number) => (s === 150 ? "2½ min" : `${s / 60} min`);
const fmtLimit = (m: number) => (m >= 120 ? `${m / 60} h` : `${m} min`);

const W = 1000;
const LBL = 196;
const RX = 980;
const ROW = 34;
const TOP = 62;
const x = (min: number) => LBL + (min / 60) * (RX - LBL);

export default function FeedCadence({ n = 9 }: { n?: number | string }) {
  const [hot, setHot] = useState<number | null>(null);
  const f = hot !== null ? FEEDS[hot] : null;
  const H = TOP + FEEDS.length * ROW + 34;
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    const i = hot ?? -1;
    let j = i;
    if (e.key === "ArrowDown") j = Math.min(FEEDS.length - 1, i + 1);
    else if (e.key === "ArrowUp") j = Math.max(0, i - 1);
    else if (e.key === "Escape") return setHot(null);
    else return;
    e.preventDefault();
    setHot(j);
  };

  return (
    <FigureFrame
      n={n}
      title="An hour of refreshes"
      className="csf-cadence"
      hint="Hover a row, or focus the chart and use the arrow keys"
      readout={
        f
          ? `${f.name}: refetched every ${fmtEvery(f.every)}, stale after ${fmtLimit(f.limit)}`
          : "Live bundle rebuilt every 30 s · each feed on its own clock"
      }
      legend={
        <ul className="csf-keys">
          <li className="csf-key">
            <span className="fc-key-tick" aria-hidden="true" /> A refetch from the source
          </li>
          <li className="csf-key">
            <span className="fc-key-limit" aria-hidden="true" /> Age at which the feed is called stale
          </li>
          <li className="csf-key">
            <span className="fc-key-check" aria-hidden="true" /> Freshness check, every 5 min
          </li>
        </ul>
      }
      caption={
        <>
          Each feed is refetched on its own clock and the newest copy goes into a bundle rebuilt every 30 seconds. The stale limit is
          several refreshes long, so one missed fetch never trips it. A feed past its limit, on two checks in a row, is reported,
          and its last good copy keeps being served, marked stale.
        </>
      }
    >
      <div className="fc">
        <svg
          className="csf-svg fc-svg csf-focus csf-desk"
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          tabIndex={0}
          aria-label={`Timeline of one hour. ${FEEDS.map((d) => `${d.name}: every ${fmtEvery(d.every)}, stale after ${fmtLimit(d.limit)}`).join(". ")}. The live bundle is rebuilt every 30 seconds and freshness is checked every 5 minutes.`}
          onKeyDown={onKey}
          onBlur={() => setHot(null)}
          onPointerLeave={() => setHot(null)}
        >
          {/* minute axis */}
          {Array.from({ length: 13 }, (_, i) => i * 5).map((m) => (
            <g key={m}>
              <line x1={x(m)} x2={x(m)} y1={TOP - 6} y2={H - 30} className={m % 15 === 0 ? "fc-grid-major" : "fc-grid"} />
              {m % 15 === 0 && (
                <text x={x(m)} y={H - 12} textAnchor="middle" className="fc-axis">
                  {m === 0 ? "0 min" : m}
                </text>
              )}
            </g>
          ))}
          {/* bundle rebuild + freshness checks */}
          <text x={LBL - 14} y={22} textAnchor="end" className="fc-lane-label">
            Live bundle, 30 s
          </text>
          {Array.from({ length: 121 }, (_, i) => (
            <line key={i} x1={x(i / 2)} x2={x(i / 2)} y1={14} y2={26} className="fc-bundle" />
          ))}
          <text x={LBL - 14} y={46} textAnchor="end" className="fc-lane-label">
            Freshness check, 5 min
          </text>
          {Array.from({ length: 13 }, (_, i) => (
            <circle key={i} cx={x(i * 5)} cy={42} r={3.2} className="fc-check" />
          ))}

          {FEEDS.map((d, i) => {
            const y = TOP + i * ROW + ROW / 2;
            const ticks = Math.floor(3600 / d.every);
            const within = d.limit <= 60;
            return (
              <g
                key={d.name}
                className="fc-row"
                data-tone={d.tone}
                data-hot={hot === i ? "" : undefined}
                data-dim={hot !== null && hot !== i ? "" : undefined}
                onPointerEnter={() => setHot(i)}
              >
                <rect x={0} y={y - ROW / 2} width={W} height={ROW} className="fc-hit" />
                <text x={LBL - 14} y={y + 4} textAnchor="end" className="fc-name">
                  {d.name}
                </text>
                <line x1={x(0)} x2={RX} y1={y} y2={y} className="fc-rail" />
                {Array.from({ length: ticks + 1 }, (_, k) => (
                  <line key={k} x1={x((k * d.every) / 60)} x2={x((k * d.every) / 60)} y1={y - 7} y2={y + 7} className="fc-tick" />
                ))}
                {within ? (
                  <g className="fc-limit">
                    <path d={`M${x(0)} ${y + 11} H${x(d.limit)}`} className="fc-span" />
                    <path d={`M${x(d.limit)} ${y - 11} V${y + 11}`} className="fc-stop" />
                    <text x={d.limit >= 60 ? x(d.limit) - 6 : x(d.limit) + 6} y={y - 3} textAnchor={d.limit >= 60 ? "end" : "start"} className="fc-limit-label">
                      stale at {fmtLimit(d.limit)}
                    </text>
                  </g>
                ) : (
                  <g className="fc-limit">
                    <path d={`M${x(0)} ${y + 11} H${RX - 4}`} className="fc-span" />
                    <path d={`M${RX - 9} ${y + 6} L${RX - 2} ${y + 11} L${RX - 9} ${y + 16}`} className="fc-stop fc-arrow" />
                    <text x={RX - 4} y={y - 9} textAnchor="end" className="fc-limit-label fc-limit-off">
                      stale at {fmtLimit(d.limit)}
                    </text>
                  </g>
                )}
                <text x={x(d.every / 60) + 4} y={y - 9} className="fc-every">
                  {hot === i ? `every ${fmtEvery(d.every)}` : ""}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="fc-phone csf-phone">
          <p className="fc-phone-top">
            <span className="csf-mono">30 s</span> live bundle rebuild · <span className="csf-mono">5 min</span> freshness check
          </p>
          <ul className="fc-list">
            {FEEDS.map((d) => (
              <li key={d.name} className="fc-item" data-tone={d.tone}>
                <span className="fc-item-name">{d.name}</span>
                <span className="fc-item-vals csf-mono">
                  every {fmtEvery(d.every)} · stale at {fmtLimit(d.limit)}
                </span>
                <span className="fc-item-strip" aria-hidden="true">
                  {Array.from({ length: Math.min(40, Math.floor((d.limit * 60) / d.every)) }, (_, k) => (
                    <span key={k} />
                  ))}
                </span>
                <span className="fc-item-note">{Math.floor((d.limit * 60) / d.every)} refetches before it is stale</span>
              </li>
            ))}
          </ul>
        </div>
        <table className="csf-sr">
          <caption>Refresh and stale limit by feed</caption>
          <thead>
            <tr>
              <th>Feed</th>
              <th>Refetched every</th>
              <th>Stale after</th>
            </tr>
          </thead>
          <tbody>
            {FEEDS.map((d) => (
              <tr key={d.name}>
                <td>{d.name}</td>
                <td>{fmtEvery(d.every)}</td>
                <td>{fmtLimit(d.limit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </FigureFrame>
  );
}
