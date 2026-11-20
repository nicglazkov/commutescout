"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay, useLoop } from "./use-play";

// 3. One incident's journey, second by second. The timings follow the code paths:
// - TTLCache.get: a copy at or past its 60 s refresh time is SERVED (old) and refreshed in
//   the background, so the build that notices the age still ships the old copy;
// - snapshot: live.json.gz is rebuilt every 30 s and uploaded only when markers changed;
// - edge: max-age=15; the map checks every 30 s with an ETag (304 when unchanged).
// The clock times are an example; the gaps between them are what the code produces.

const T0 = 8 * 3600 + 13 * 60 + 30; // 08:13:30
const SPAN = 120;
const X0 = 168;
const X1 = 806;
const sx = (c: number) => X0 + ((X1 - X0) * (c - T0)) / SPAN;
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
const BUILDS = [at(13, 41), at(14, 11), REFRESH, PUBLISH];
const CHECKS = [at(13, 50), at(14, 20), at(14, 50), SHOWN];

const ROWS = [
  { key: "agency", label: "Agency feed", y: 46 },
  { key: "copy", label: "Our copy", y: 104 },
  { key: "pub", label: "live.json.gz build", y: 170 },
  { key: "map", label: "Your map", y: 226 },
] as const;
type Row = (typeof ROWS)[number]["key"];
const Y = Object.fromEntries(ROWS.map((r) => [r.key, r.y])) as Record<Row, number>;
const AXIS = 264;

// The same story as a log, for the phone layout.
type Log = { t: number; row: Row; k: string; text: string; key?: boolean };
const LOG: Log[] = [
  { t: OLD_COPY, row: "copy", k: "neutral", text: "Our copy of the feed is fetched. No crash yet." },
  { t: at(13, 41), row: "pub", k: "neutral", text: "Nothing changed, not uploaded." },
  { t: at(13, 50), row: "map", k: "ok", text: "304, nothing new." },
  { t: LOGGED, row: "agency", k: "incident", text: "A dispatcher logs a crash at Exit 14.", key: true },
  { t: at(14, 11), row: "pub", k: "neutral", text: "Our copy is 30 s old, still fresh. Nothing changed." },
  { t: at(14, 20), row: "map", k: "ok", text: "304, nothing new." },
  { t: REFRESH, row: "pub", k: "stale", text: "Our copy is 60 s old. It is served once more, and a new copy is fetched behind it.", key: true },
  { t: NEW_COPY, row: "copy", k: "incident", text: "The new copy lands, with the crash in it.", key: true },
  { t: at(14, 50), row: "map", k: "ok", text: "304. The new copy is not in a build yet." },
  { t: PUBLISH, row: "pub", k: "accent", text: "Changed: live.json.gz is uploaded.", key: true },
  { t: SHOWN, row: "map", k: "incident", text: "200. The pin appears on your map.", key: true },
];
const ROW_NAME: Record<Row, string> = { agency: "Agency", copy: "Our copy", pub: "Build", map: "Map check" };

export default function D03Journey() {
  const { ref, play } = usePlay<HTMLDivElement>();
  const t = useLoop(play, 18, 1);
  const now = T0 + t * SPAN;
  const seen = (c: number) => now >= c;
  const dim = (c: number) => (seen(c) ? 1 : 0.15);
  return (
    <FigureFrame
      n={3}
      title="One crash, from the agency to your map"
      hint="An example morning; the gaps are what the code produces"
      readout={fmt(Math.min(now, T0 + SPAN))}
      caption={
        <>
          A dispatcher logs a crash at 08:14:05. Our copy of that feed was fetched at 08:13:41, so the build at 08:14:41
          finds it 60 seconds old, ships it anyway and fetches a new copy behind it. The next build, 30 seconds later,
          includes the crash and uploads a new file; the map&apos;s next check gets it. Here that is 75 seconds. The
          longest it can take is a little under three minutes: the 60-second refresh time, up to 30 s for a build to
          notice, 30 s to the next build, 15 s at the edge and 30 s to the map&apos;s next check.
        </>
      }
    >
      <div ref={ref} className="dgf" data-play={play ? "" : undefined}>
        <div className="csf-desk">
          <svg className="csf-svg" viewBox="0 0 820 322" role="img" aria-label="Timeline from 08:13:30 to 08:15:30. The agency logs a crash at 08:14:05. Our copy, fetched at 08:13:41, is still served by the 08:14:41 build, which fetches a new copy behind it; the new copy lands at 08:14:42. Builds run every 30 seconds; the 08:15:11 build is the first with the crash and uploads it. The map's check at 08:15:20 gets a 200 and the pin appears, 75 seconds after the crash was logged.">
            {Array.from({ length: 5 }, (_, i) => {
              const c = T0 + i * 30;
              return (
                <g key={i}>
                  <line className="grid" x1={sx(c)} x2={sx(c)} y1={22} y2={AXIS} />
                  <text className="t-mono t-m" x={sx(c)} y={AXIS + 20} textAnchor={i === 4 ? "end" : "middle"}>{fmt(c)}</text>
                </g>
              );
            })}
            {ROWS.map((r) => (
              <g key={r.key}>
                <text className="t-strong t-l" x={0} y={r.y + 4.5}>{r.label}</text>
                <line className="rule" x1={X0} x2={X1} y1={r.y} y2={r.y} />
              </g>
            ))}

            {/* agency */}
            <g data-k="incident" opacity={dim(LOGGED)}>
              <circle className="dot-k" cx={sx(LOGGED)} cy={Y.agency} r={6} />
              <text className="t-mono-ink t-m" x={sx(LOGGED) + 11} y={Y.agency - 10}>{fmt(LOGGED)} crash logged at Exit 14</text>
            </g>

            {/* our copy: the old one, the moment it is refetched, the new one */}
            <rect x={sx(OLD_COPY)} y={Y.copy - 7} width={sx(REFRESH) - sx(OLD_COPY)} height={14} rx={3} className="fill-lo" />
            <text className="t-mono t-m" x={sx(OLD_COPY) + 6} y={Y.copy - 13}>copy from {fmt(OLD_COPY)} · no crash</text>
            <rect x={sx(REFRESH)} y={Y.copy - 7} width={sx(NEW_COPY) - sx(REFRESH) + 0.5} height={14} className="fill-stale" />
            <text className="t-mono t-m" x={sx(REFRESH) - 6} y={Y.copy + 25} textAnchor="end">60 s old: served once more</text>
            <g data-k="incident" opacity={dim(NEW_COPY)}>
              <rect className="box-k" x={sx(NEW_COPY)} y={Y.copy - 7} width={X1 - sx(NEW_COPY)} height={14} rx={3} />
              <text className="t-mono-ink t-m" x={sx(NEW_COPY) + 4} y={Y.copy + 25}>{fmt(NEW_COPY)} new copy, with the crash</text>
            </g>

            {/* builds every 30 s */}
            {BUILDS.map((c) => {
              const hit = c === PUBLISH;
              const stale = c === REFRESH;
              return (
                <g key={c} data-k={hit ? "accent" : "neutral"} opacity={hit ? dim(c) : 1}>
                  <rect className={hit ? "bar-k" : stale ? "fill-stale" : "fill-lo"} x={sx(c) - 3.5} y={Y.pub - 8} width={7} height={16} rx={1.5} />
                  <text className={hit ? "t-k t-m" : "t-mono t-m"} x={sx(c)} y={Y.pub + 25} textAnchor="middle">{hit ? "changed: upload" : stale ? "same; asks for a new copy" : "same: skip"}</text>
                  {stale && <path className="wire-stale" d={`M${sx(c)} ${Y.pub - 9}V${Y.copy + 8}`} />}
                </g>
              );
            })}

            {/* map checks every 30 s */}
            {CHECKS.map((c) => {
              const hit = c === SHOWN;
              return (
                <g key={c} data-k={hit ? "incident" : "ok"} opacity={hit ? dim(c) : 1}>
                  <circle className={hit ? "dot-k" : "ring-k"} cx={sx(c)} cy={Y.map} r={hit ? 6 : 4.5} />
                  <text className={hit ? "t-k t-m" : "t-mono t-m"} x={hit ? X1 : sx(c)} y={Y.map + 24} textAnchor={hit ? "end" : "middle"}>{hit ? "200: new pin" : "304"}</text>
                </g>
              );
            })}

            {/* the 75 s bracket */}
            <g opacity={seen(SHOWN) ? 1 : 0}>
              <path className="wire-dash" d={`M${sx(LOGGED)} 318V310H${sx(SHOWN)}V318`} />
              <rect x={(sx(LOGGED) + sx(SHOWN)) / 2 - 124} y={300} width={248} height={20} className="knock" />
              <text className="t-strong t-l" x={(sx(LOGGED) + sx(SHOWN)) / 2} y={315} textAnchor="middle">75 s from logged to on your map</text>
            </g>

            {play && <line x1={sx(now)} x2={sx(now)} y1={22} y2={AXIS} className="playhead" />}
          </svg>
        </div>
        <div className="csf-phone">
          <ol className="dg-log-list">
            {LOG.map((e, i) => (
              <li key={i} className="dg-log" data-k={e.k} data-key={e.key ? "" : undefined} data-seen={seen(e.t) ? "" : undefined}>
                <span className="dg-log-t">{fmt(e.t)}</span>
                <span className="dg-log-row">{ROW_NAME[e.row]}</span>
                <span className="dg-log-x">{e.text}</span>
              </li>
            ))}
          </ol>
          <p className="dg-log-sum" data-seen={seen(SHOWN) ? "" : undefined}>75 s from logged to on your map</p>
        </div>
      </div>
    </FigureFrame>
  );
}
