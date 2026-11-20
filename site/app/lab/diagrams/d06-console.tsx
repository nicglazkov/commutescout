"use client";

import { FigureFrame } from "@/components/figures/frame";
import { usePlay, useLoop } from "./use-play";

// 6. Feed health console. Columns and rules are /api/sources (app.source_health):
// status is "down" when nothing can be served, "stale" when the last refresh failed or the
// copy is older than its limit, otherwise "fresh". Limits are freshness.py's (California
// feeds per kind, every other state 90 min, camera lists 7 h). Ages are an example.

type Src = { name: string; sub: string; every: number; age: number; limit: number; status: "fresh" | "stale" | "down"; note?: string };
const SRC: Src[] = [
  { name: "Highway patrol incidents", sub: "XML · refresh 60 s", every: 60, age: 42, limit: 20 * 60, status: "fresh" },
  { name: "Lane closures", sub: "XML, 12 districts · refresh 5 min", every: 300, age: 3 * 60 + 10, limit: 30 * 60, status: "fresh" },
  { name: "Chain controls", sub: "XML · refresh 5 min", every: 300, age: 1 * 60 + 55, limit: 30 * 60, status: "fresh" },
  { name: "Wildfires", sub: "ArcGIS · refresh 5 min", every: 300, age: 2 * 60 + 10, limit: 60 * 60, status: "fresh" },
  { name: "A state DOT", sub: "JSON · refresh 3 min", every: 180, age: 22 * 60, limit: 90 * 60, status: "stale", note: "last refresh failed: still served, marked stale" },
  { name: "A work-zone feed", sub: "WZDx · refresh 10 min", every: 600, age: 9 * 60 + 30, limit: 90 * 60, status: "fresh" },
  { name: "Another state DOT", sub: "XML · refresh 3 min", every: 180, age: 0, limit: 90 * 60, status: "down", note: "no good copy in 30 min: nothing served" },
  { name: "A camera list", sub: "inventory · refresh 10 min", every: 600, age: 6 * 60 + 40, limit: 7 * 3600, status: "fresh" },
];

const K = { fresh: "ok", stale: "stale", down: "incident" } as const;

const fmtAge = (s: number) => {
  if (s < 60) return `${Math.floor(s)} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${String(Math.floor(s % 60)).padStart(2, "0")} s`;
  return `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")} min`;
};
const fmtLimit = (s: number) => (s >= 3600 && s % 3600 === 0 ? `${s / 3600} h` : `${s / 60} min`);

export default function D06Console() {
  const { ref, play } = usePlay<HTMLDivElement>();
  // ages tick up in real time while on screen; a refresh drops a fresh feed back to 0
  const t = useLoop(play, 60, 0);
  const tick = t * 60;
  const counts = SRC.reduce((a, s) => ((a[s.status] += 1), a), { fresh: 0, stale: 0, down: 0 });
  return (
    <FigureFrame
      n={6}
      title="Every source, with its age"
      hint="The bar is the age of the last good copy; the line is when it counts as stale"
      readout={`${counts.fresh} fresh · ${counts.stale} stale · ${counts.down} down`}
      caption={
        <>
          The same view the apps&apos; data-source screen and <code>/api/sources</code> give. A source whose refresh
          fails keeps its last good copy on the map, marked stale; one with no good copy left is down and shows nothing.
          Every five minutes a check looks for sources past their limit, and two failed checks in a row raise an alert.
        </>
      }
    >
      <div ref={ref} className="dgf" style={{ overflowX: "auto" }}>
        <table className="dg-con">
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col">Age of last good copy</th>
              <th scope="col" style={{ width: "34%" }}>
                <span className="csf-sr">Age against limit</span>
              </th>
              <th scope="col">Stale after</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {SRC.map((s) => {
              const live = s.status === "down" ? null : s.status === "fresh" ? (s.age + tick) % s.every : s.age + tick;
              const age = live ?? 0;
              return (
                <tr key={s.name} data-k={K[s.status]}>
                  <td className="src">
                    {s.name}
                    <span className="sub">{s.note ?? s.sub}</span>
                  </td>
                  <td className="num">{live === null ? "none" : fmtAge(age)}</td>
                  <td>
                    <div className="dg-age" aria-hidden="true">
                      <i style={{ width: `${Math.min(100, (age / s.limit) * 100 * 0.8)}%` }} />
                      <b style={{ left: "80%" }} />
                    </div>
                  </td>
                  <td className="num">{fmtLimit(s.limit)}</td>
                  <td>
                    <span className="dg-pill">{s.status}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </FigureFrame>
  );
}
