// Dev-only stand-in for /api/hero-dots (src/ca_roads_demo/hero_dots.py)
// until that endpoint is deployed. Next serves this file only on the dev
// server (the "lab.ts" page extension; see next.config.ts), and a local
// route wins over the dev proxy of /api/* to production. It reads the
// live production /api/mapdata and reduces it exactly like hero_dots.py,
// so the local preview shows the real live dots.
const KINDS: Record<string, string> = {
  incident: "i", lane_closure: "c", chain_control: "h", wildfire: "f",
};
const SRC = "https://commutescout.com/api/mapdata?bbox=-85,-180,85,180&kinds=incident,closure,chain,fire&slim=1";

export const dynamic = "force-static";

type Marker = { kind?: string; lat?: number; lon?: number };
let cache: { at: number; body: string } | null = null;


export async function GET() {
  if (!cache || Date.now() - cache.at > 30_000) {
    const r = await fetch(SRC, { cache: "no-store" });
    if (!r.ok) return new Response("upstream " + r.status, { status: 502 });
    const { markers } = (await r.json()) as { markers: Marker[] };
    const out: Record<string, number[]> = { i: [], c: [], h: [], f: [] };
    const seen = new Set<string>();
    for (const m of markers) {
      const k = m.kind ? KINDS[m.kind] : undefined;
      if (!k || typeof m.lat !== "number" || typeof m.lon !== "number") continue;
      const lat = Math.round(m.lat * 100) / 100, lon = Math.round(m.lon * 100) / 100;
      const key = `${k}${lat},${lon}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out[k].push(lat, lon);
    }
    const at = new Date().toISOString().replace(/\.\d+Z$/, "+00:00");
    cache = { at: Date.now(), body: JSON.stringify({ at, ...out }) };
  }
  return new Response(cache.body, {
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
