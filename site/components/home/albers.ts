// Albers equal-area conic with d3's geoAlbersUsa lower-48 parameters
// (parallels 29.5 and 45.5, centre 38.7 N 96 W, scale 1300, translate to
// the middle of a 975 x 610 frame), so a latitude and longitude land on
// the same pixel as the state outlines in figures/us-map.geo.ts.
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

/** The lower 48 only: Alaska and Hawaii are drawn as insets, not in place. */
export function inLower48(lat: number, lon: number): boolean {
  return lat > 24 && lat < 50 && lon > -125.5 && lon < -66;
}
