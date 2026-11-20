"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay, useLoop } from "./use-play";

// 3. One incident's journey, second by second. The timings follow the code paths:
// - TTLCache.get: a copy past its 60 s refresh time is SERVED (old) and refreshed in the
//   background, so the build that notices the age still ships the old copy;
// - snapshot: live.json.gz is rebuilt every 30 s and uploaded only when markers changed;
// - edge: max-age=15; the map checks every 30 s with an ETag (304 when unchanged).
// The clock times are an example; the gaps between them are what the code produces.

const T0 = 8 * 3600 + 13 * 60 + 30; // 08:13:30
const SPAN = 120;
const X0 = 150;
const X1 = 704;
const sx = (clock: number) => X0 + ((X1 - X0) * (clock - T0)) / SPAN;
const at = (m: number, s: number) => 8 * 3600 + m * 60 + s;
const fmt = (c: number) => {
  const h = Math.floor(c / 3600);
  const m = Math.floor((c % 3600) / 60);
  const s = Math.floor(c % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};

const LOGGED = at(14, 5);
const OLD_COPY = at(13, 41);
const REFRESH = at(14, 41);
const NEW_COPY = at(14, 42);
const PUBLISH = at(15, 11);
const SHOWN = at(15, 20);

const ROWS = [
  { key: "agency", label: "Agency feed", y: 50 },
  { key: "copy", label: "Our copy in memory", y: 96 },
  { key: "pub", label: "live.json.gz build", y: 142 },
  { key: "map", label: "Your map", y: 188 },
];

export default function D03Journey() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const t = useLoop(play, 16, 1);
  const now = T0 + t * SPAN;
  const seen = (c: number) => now >= c;
  const y = Object.fromEntries(ROWS.map((r) => [r.key, r.y])) as Record<string, number>;
  return (
    <FigureFrame
      n={3}
      title="One crash, from the agency to your map"
      hint="An example morning; the gaps are what the code produces"
      readout={fmt(Math.min(now, T0 + SPAN))}
      caption={
        <>
          A dispatcher logs a crash at 08:14:05. Our copy of that feed was fetched at 08:13:41, so the build at 08:14:41
          finds it a minute old, ships it anyway and fetches a new copy behind it. The next build, 30 seconds later,
          includes the crash and uploads a new file; the map&apos;s next check gets it. Here that is 75 seconds. The longest it can take is a little under three
          minutes: the 60-second refresh time, up to 30 s for a build to notice, 30 s to the next build, 15 s at the
          edge and 30 s to the map&apos;s next check.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <svg className="csf-svg" viewBox="0 0 720 262" role="img" aria-label="Timeline from 08:13:30 to 08:15:30. The agency logs a crash at 08:14:05. Our cached copy, fetched at 08:13:41, is refreshed at 08:14:41 in the background and the new copy lands at 08:14:42. Builds run every 30 seconds; the 08:15:11 build is the first with the crash. The map's check at 08:15:20 gets the new file and the pin appears.">
          {Array.from({ length: 5 }, (_, i) => {
            const c = T0 + i * 30;
            return (
              <g key={i}>
                <line className="grid" x1={sx(c)} x2={sx(c)} y1={28} y2={214} />
                <text className="t-mono" x={sx(c)} y={230} textAnchor="middle">{fmt(c).slice(0, 8)}</text>
              </g>
            );
          })}
          {ROWS.map((r) => (
            <g key={r.key}>
              <text className="t-strong" x={0} y={r.y + 4}>{r.label}</text>
              <line className="rule" x1={X0} x2={X1} y1={r.y} y2={r.y} />
            </g>
          ))}

          {/* agency */}
          <g data-k="incident">
            <circle className="dot-k" cx={sx(LOGGED)} cy={y.agency} r={5} />
            <text className="t-mono-ink" x={sx(LOGGED) + 9} y={y.agency - 8}>{fmt(LOGGED)} crash logged at Exit 14</text>
          </g>

          {/* our copy: old copy bar, then new copy bar */}
          <g data-k="neutral">
            <rect x={sx(OLD_COPY)} y={y.copy - 6} width={sx(REFRESH) - sx(OLD_COPY)} height={12} rx={3} fill="var(--f-faint)" />
            <text className="t-mono" x={sx(OLD_COPY) + 6} y={y.copy - 10}>copy from {fmt(OLD_COPY)} · no crash</text>
          </g>
          <g data-k="stale">
            <rect x={sx(REFRESH)} y={y.copy - 6} width={sx(NEW_COPY) - sx(REFRESH) + 0.5} height={12} fill="var(--f-stale)" />
          </g>
          <g data-k="incident" opacity={seen(NEW_COPY) ? 1 : 0.15}>
            <rect className="box-k" x={sx(NEW_COPY)} y={y.copy - 6} width={X1 - sx(NEW_COPY)} height={12} rx={3} />
            <text className="t-mono" x={sx(NEW_COPY) + 4} y={y.copy + 22}>{fmt(NEW_COPY)} new copy, crash included</text>
          </g>
          <text className="t-mono" x={sx(REFRESH) - 4} y={y.copy + 22} textAnchor="end">60 s old: served, refetched behind it</text>

          {/* builds every 30 s */}
          {[at(13, 41), at(14, 11), at(14, 41), PUBLISH].map((c) => {
            const hit = c === PUBLISH;
            return (
              <g key={c} data-k={hit ? "accent" : "neutral"} opacity={hit && !seen(c) ? 0.15 : 1}>
                <rect className={hit ? "bar-k" : undefined} fill={hit ? undefined : "var(--f-lo)"} x={sx(c) - 3} y={y.pub - 7} width={6} height={14} rx={1.5} />
                <text className="t-mono" x={sx(c)} y={y.pub + 22} textAnchor="middle">{hit ? "changed: upload" : "same: skip"}</text>
              </g>
            );
          })}

          {/* map checks every 30 s */}
          {[at(13, 50), at(14, 20), at(14, 50), SHOWN].map((c) => {
            const hit = c === SHOWN;
            return (
              <g key={c} data-k={hit ? "incident" : "ok"} opacity={hit && !seen(c) ? 0.15 : 1}>
                <circle className={hit ? "dot-k" : "ring-k"} cx={sx(c)} cy={y.map} r={hit ? 5 : 3.5} />
                <text className="t-mono" x={sx(c)} y={y.map + 20} textAnchor="middle">{hit ? "200: new pin" : "304"}</text>
              </g>
            );
          })}

          {/* the 75 s bracket */}
          <g opacity={seen(SHOWN) ? 1 : 0}>
            <path className="wire-dash" d={`M${sx(LOGGED)} 248V242H${sx(SHOWN)}V248`} />
            <text className="t-strong" x={(sx(LOGGED) + sx(SHOWN)) / 2} y={258} textAnchor="middle">75 s from logged to on your map</text>
          </g>

          {/* playhead */}
          {play && (
            <line x1={sx(now)} x2={sx(now)} y1={28} y2={214} stroke="var(--f-accent)" strokeWidth={1.2} />
          )}
        </svg>
      </div>
    </FigureFrame>
  );
}
