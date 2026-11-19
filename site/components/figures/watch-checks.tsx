"use client";

import { useEffect, useRef, useState } from "react";
import { AppWindow, Mail, Smartphone } from "lucide-react";
import { FigureFrame } from "./frame";
import { useInView, useReducedMotion } from "./hooks";

// One watch area, three checks five minutes apart. Every rule below is in src/ca_roads_demo/watch.py:
// - checks run every 5 minutes (Cloud Scheduler "*/5 * * * *", docs/deploy.md:325-330 -> api_check_watches, watch.py:2135)
// - the first check of a watch seeds the seen-set silently: first_run = raw_seen is None (watch.py:1973-1974),
//   alerts only `if not first_run and fresh` (watch.py:2013)
// - later checks alert only on matched events not already seen (watch.py:1985); ids stay seen for 6 h after
//   they vanish (SEEN_GRACE_SECONDS, watch.py:91) so a flapping event never re-alerts
// - only incidents, closures, chain controls and fires can alert: WATCH_KINDS (watch.py:110); signs,
//   cameras and weather are never collected for alerts (_collect_events, watch.py:1394-1495)
// - "inside" is the event's point inside the drawn shape (watch_matches, watch.py:505-522)
// - channels default push on, email off (watch.py:1075-1076); push reaches both the phone app (FCM) and
//   browser web push subscriptions (_push_to_subs, watch.py:1549); email needs the account and watch
//   both opted in (watch.py:1957-1960)

type Step = 0 | 1 | 2 | 3;
const CHECKS = [
  { n: 1, at: "0 min", title: "First check", result: "Baseline: the incident inside is recorded as seen. Nothing is sent." },
  { n: 2, at: "+5 min", title: "Second check", result: "A new incident inside: one alert. The closure outside and the sign are ignored." },
  { n: 3, at: "+10 min", title: "Third check", result: "Nothing new since the last check. Nothing is sent." },
] as const;

const AREA = "M70 46 L188 30 L226 98 L176 150 L86 138 Z";
const AREA_PTS: [number, number][] = [
  [70, 46],
  [188, 30],
  [226, 98],
  [176, 150],
  [86, 138],
];

function Incident({ x, y, isNew }: { x: number; y: number; isNew?: boolean }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      {isNew && <circle className="wc-ring" r={11} />}
      <circle className="wc-pin" r={7.5} fill="var(--f-incident)" />
      <path d="M0 -3.6 V0.8" className="wc-glyph" />
      <circle cy={3.4} r={0.95} className="wc-glyph-dot" />
    </g>
  );
}
function Closure({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle className="wc-pin" r={7.5} fill="var(--f-closure)" />
      <path d="M-3.6 0 H3.6" className="wc-glyph" />
    </g>
  );
}
function Sign({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <path d="M0 6 V12" className="wc-post" />
      <rect x={-9} y={-6} width={18} height={12} rx={2.2} className="wc-sign" />
      <path d="M-5.5 -1.8 H5.5 M-5.5 1.8 H2.5" className="wc-sign-ink" />
    </g>
  );
}
function Tag({ x, y, text, tone, anchor = "start" }: { x: number; y: number; text: string; tone: "alert" | "quiet" | "seen"; anchor?: "start" | "end" }) {
  const w = text.length * 5.1 + 12;
  const x0 = anchor === "end" ? x - w : x;
  return (
    <g className="wc-tag" data-tone={tone}>
      <rect x={x0} y={y - 8} width={w} height={16} rx={8} />
      <text x={x0 + w / 2} y={y + 3.2} textAnchor="middle">
        {text}
      </text>
    </g>
  );
}

function MiniMap({ check }: { check: 1 | 2 | 3 }) {
  return (
    <svg viewBox="0 0 280 184" className="csf-svg wc-map" aria-hidden="true">
      <rect x={0.5} y={0.5} width={279} height={183} rx={9} className="wc-paper" />
      <g className="wc-streets">
        <path d="M0 64 H280 M0 118 H280 M44 0 V184 M104 0 V184 M236 0 V184" />
      </g>
      <path d="M-6 150 C 50 140, 96 104, 140 98 S 230 52, 290 30" className="wc-road-o" />
      <path d="M-6 150 C 50 140, 96 104, 140 98 S 230 52, 290 30" className="wc-road" />
      <path d="M160 -6 C 150 52, 166 120, 150 190" className="wc-road-o" />
      <path d="M160 -6 C 150 52, 166 120, 150 190" className="wc-road" />
      <path d={AREA} className="wc-area" />
      {AREA_PTS.map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r={3} className="wc-handle" />
      ))}
      <Sign x={128} y={58} />
      <Incident x={106} y={113} />
      {check >= 2 && <Incident x={190} y={78} isNew={check === 2} />}
      {check >= 2 && <Closure x={258} y={36} />}
      {check === 1 && <Tag x={120} y={136} text="seen, not sent" tone="seen" />}
      {check === 2 && (
        <>
          <Tag x={176} y={104} text="new: alert" tone="alert" anchor="start" />
          <Tag x={250} y={58} text="outside" tone="quiet" anchor="end" />
          <Tag x={114} y={46} text="signs never alert" tone="quiet" anchor="end" />
        </>
      )}
      {check === 3 && <Tag x={136} y={136} text="all seen" tone="seen" />}
    </svg>
  );
}

export default function WatchChecks({ n = 3 }: { n?: number | string }) {
  const root = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const inView = useInView(root);
  const [step, setStep] = useState<Step>(0);
  const [email, setEmail] = useState(false);
  const played = useRef(false);

  // a single calm tour the first time the figure is seen; ends on the full picture
  useEffect(() => {
    if (!inView || reduced || played.current) return;
    played.current = true;
    const seq: Step[] = [1, 2, 3, 0];
    const timers = seq.map((s, i) => window.setTimeout(() => setStep(s), 400 + i * 2600));
    return () => timers.forEach(clearTimeout);
  }, [inView, reduced]);

  const lit = step === 0 || step >= 2;
  const channels = ["app push", "browser push", ...(email ? ["email"] : [])];
  const readout =
    step === 1
      ? "Check 1 · 1 seen · 0 sent"
      : step === 3
        ? "Check 3 · 0 new · 0 sent"
        : `Check 2 · 1 new inside · 1 alert to ${channels.join(", ")}`;

  return (
    <FigureFrame
      n={n}
      title="One watch area, three checks"
      className="csf-watch"
      hint="Step through the checks, or switch email on"
      readout={readout}
      controls={
        <div className="csf-controls" role="group" aria-label="Show a check">
          {([0, 1, 2, 3] as Step[]).map((s) => (
            <button key={s} type="button" className="csf-chip" aria-pressed={step === s} onClick={() => setStep(s)}>
              {s === 0 ? "All three" : `Check ${s}`}
            </button>
          ))}
        </div>
      }
      caption={
        <>
          An area is checked every five minutes. The <b>first check</b> only records what is already there, so a new area never
          floods you with old news. After that, an alert goes out for each <b>new</b> incident, closure, chain control or wildfire
          whose position is inside the shape. Signs, cameras and weather never alert, and an event already sent stays quiet even if
          it drops out and comes back.
        </>
      }
    >
      <div ref={root} className="wc" data-step={step}>
        <div className="wc-axis" aria-hidden="true">
          <span className="wc-axis-line" />
          {CHECKS.map((c) => (
            <span key={c.n} className="wc-axis-tick">
              <span className="wc-axis-dot" />
              {c.at}
            </span>
          ))}
        </div>
        <ol className="wc-checks">
          {CHECKS.map((c) => (
            <li key={c.n} className="wc-check" data-dim={step !== 0 && step !== c.n ? "" : undefined} data-alert={c.n === 2 ? "" : undefined}>
              <div className="wc-check-head">
                <span className="wc-check-n">{c.n}</span>
                <span className="wc-check-title">{c.title}</span>
                <span className="wc-check-at csf-mono">{c.at}</span>
              </div>
              <MiniMap check={c.n} />
              <p className="wc-result">
                <span className="wc-result-dot" data-sent={c.n === 2 ? "" : undefined} aria-hidden="true" />
                {c.result}
              </p>
            </li>
          ))}
        </ol>
        <div className="wc-fan" data-lit={lit ? "" : undefined}>
          <div className="wc-bus" aria-hidden="true" data-email={email ? "" : undefined}>
            <span className="wc-bus-stem" />
            <span className="wc-bus-l" />
            <span className="wc-bus-r" />
            <span className="wc-bus-drop" data-at="1" />
            <span className="wc-bus-drop" data-at="2" />
            <span className="wc-bus-drop" data-at="3" />
          </div>
          <p className="wc-fan-label">The alert from check 2 goes to</p>
          <ul className="wc-channels">
            <li className="wc-channel" data-on="">
              <Smartphone className="wc-ch-icon" aria-hidden="true" />
              <span className="wc-ch-text">
                <b>App push</b>
                <span>On by default</span>
              </span>
            </li>
            <li className="wc-channel" data-on="">
              <AppWindow className="wc-ch-icon" aria-hidden="true" />
              <span className="wc-ch-text">
                <b>Browser push</b>
                <span>Same push setting</span>
              </span>
            </li>
            <li className="wc-channel" data-on={email ? "" : undefined}>
              <Mail className="wc-ch-icon" aria-hidden="true" />
              <span className="wc-ch-text">
                <b>Email</b>
                <span>{email ? "On: one email per area per check" : "Off by default"}</span>
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={email}
                aria-label="Email alerts"
                className="wc-switch csf-focus"
                onClick={() => setEmail((v) => !v)}
              >
                <span />
              </button>
            </li>
          </ul>
        </div>
      </div>
    </FigureFrame>
  );
}
