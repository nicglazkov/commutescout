// Albers equal-area conic with the parameters d3's geoAlbersUsa uses for the lower 48
// (parallels 29.5 and 45.5, rotate 96 W, center 38.7 N, scale 1300, translate 487.5, 305),
// so lat/lon land on the same 975 x 610 frame as components/figures/us-map.geo.ts.
const R = Math.PI / 180;
const p0 = 29.5 * R;
const p1 = 45.5 * R;
const n = (Math.sin(p0) + Math.sin(p1)) / 2;
const c = 1 + Math.sin(p0) * (2 * n - Math.sin(p0));
const r0 = Math.sqrt(c) / n;
const K = 1300;

function raw(lam: number, phi: number): [number, number] {
  const r = Math.sqrt(c - 2 * n * Math.sin(phi)) / n;
  return [r * Math.sin(lam * n), r0 - r * Math.cos(lam * n)];
}
const ctr = raw(-0.6 * R, 38.7 * R);
const dx = 487.5 - K * ctr[0];
const dy = 305 + K * ctr[1];

export function project(lat: number, lon: number): [number, number] {
  const [x, y] = raw((lon + 96) * R, lat * R);
  return [dx + K * x, dy - K * y];
}

export type Marker = { x: number; y: number; k: "i" | "c" | "h" | "f" };

export function decodeMarkers(s: string): Marker[] {
  return s.split(";").map((t) => {
    const [a, b, k] = t.split(",");
    const [x, y] = project(Number(a), Number(b));
    return { x, y, k: k as Marker["k"] };
  });
}
