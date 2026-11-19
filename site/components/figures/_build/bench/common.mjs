// Shared helpers for the Clear Coat figures (anatomy kit).
export const k = await import("../kit/iso-kit.mjs");
export const G = await import("../kit/lathe.mjs");

export const r1 = (v) => Math.round(v * 10) / 10;
export const r4 = (a) => a.map((v) => Math.round(v * 10000) / 10000);
export const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function ctx(P) {
  const at = (p) => k.iso(p, P);
  const S = (paths, style) => k.solidSvg(paths, style);
  const L = (d, style) => k.lineSvg(d, style);
  const D = (pts, style) => k.dotsSvg(pts, style);
  const depth = (x, y, z = 0) => k.depthOf([x, y, z], P);
  const byDepth = (pts) => [...pts].sort((a, b) => depth(a[0], a[1], a[2] || 0) - depth(b[0], b[1], b[2] || 0));
  const poly = (pts, cls, extra = "") => `<path class="${cls}" ${extra}d="${k.pathOf(pts.map(at), true)}"/>`;
  const line = (pts, cls, extra = "") => `<path class="${cls}" ${extra}d="${k.pathOf(pts.map(at))}"/>`;
  const halo = (plan, z, blur = 6) => `<path class="iso-halo" style="filter:blur(${blur}px)" d="${k.haloOf(plan, z, 0.1, P)}"/>`;
  const text = (m, t, size, cls = "", anchor = "middle") => `<text class="iso-face-text ${cls}" transform="${m}" font-size="${size}" text-anchor="${anchor}">${esc(t)}</text>`;
  const up = (o) => G.frameAlong(o, [0, 0, 1]);
  const { sinA, cosA } = k.cameraOf(P);
  // shade index for a vertical face with plan normal (nx, ny), same rule as k.extrude
  const shadeOf = (nx, ny) => Math.min(3, Math.max(0, Math.floor(((nx * -sinA + ny * cosA + 1) / 2) * 4)));
  const facing = (nx, ny) => nx * cosA + ny * sinA > 1e-9;

  // base plate on feet with groove, screws, optional ruler strip and label plate
  function plate(PL, { th = 10, foot = 5, feet = null, screwInset = 10, grooveInset = 5 } = {}) {
    const out = [`<path class="iso-halo" d="${k.haloOf(PL, -th - foot, th + 2, P)}"/>`];
    const fs = feet || k.corners(PL, 22);
    for (const [x, y] of byDepth(fs)) {
      out.push(S(k.cylinder(x, y, 6.4, -th - foot, 1.5, P, 8), { tone: "lo" }));
      out.push(S(k.cylinder(x, y, 5, -th - foot + 1.5, foot - 1.5, P, 8), { tone: "mid" }));
    }
    out.push(S(k.slabOf(PL, -th, th, P, 4, 1.6), { tone: "mid" }));
    out.push(L(k.planOutline(k.insetPlan(PL, grooveInset), 0, P), { tone: "lo" }));
    const screws = k.corners(PL, screwInset);
    out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 10)).join(""), { tone: "lo" }));
    out.push(D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.55 }));
    return out.join("");
  }
  function ruler(strip, step, every, { z = 0, lengths = [2, 3.6] } = {}) {
    const out = [S(k.slabOf(strip, z, 0.6, P, 3), { tone: "lo", crease: "none" })];
    const t = k.topTicks(strip.x + 3, strip.x + strip.w - 3, step, every, strip.y + 0.8, z + 0.6, lengths, P);
    out.push(L(t.minor, { tone: "lo" }), L(t.major, { tone: "mid" }));
    out.push(D([at([strip.x + 1.6, strip.y + strip.d / 2, z + 0.6]), at([strip.x + strip.w - 1.6, strip.y + strip.d / 2, z + 0.6])], { size: 0.45 }));
    return out.join("");
  }
  function labelPlate(lp, z = 0, rules = [[5, 0.62], [5, 0.44], [5, 0.7]]) {
    const out = [S(k.slabOf(lp, z, 0.8, P, 4), { tone: "mid", crease: "none" })];
    out.push(L(k.planOutline(k.insetPlan(lp, 1.4), z + 0.8, P), { tone: "faint" }));
    rules.forEach(([x0, f], i) => out.push(L(k.lineOnTop([lp.x + x0, lp.y + 3.2 + i * ((lp.d - 6.4) / 2)], [lp.x + x0 + (lp.w - 14) * f, lp.y + 3.2 + i * ((lp.d - 6.4) / 2)], z + 0.8, P), { tone: "lo", free: true })));
    out.push(D([at([lp.x + lp.w - 3.2, lp.y + 3, z + 0.8]), at([lp.x + lp.w - 3.2, lp.y + lp.d - 3, z + 0.8])], { size: 0.42 }));
    return out.join("");
  }
  // a prism along y: polygon in the x-z plane, from y0 (far) to y1 (near). Returns a kit-style solid.
  function prismY(poly2, y0, y1, { tone = "mid", topClass = "iso-top", cls = "", topSplit = null } = {}) {
    const n = poly2.length;
    const front = poly2.map(([x, z]) => at([x, y1, z]));
    const parts = [];
    // fill: union of front face, back face and every edge quad
    const fills = [k.pathOf(front, true)];
    const shadesB = [[], [], [], []];
    const tops = [];
    const edges = [];
    // signed area to know outward normals (x right, z up)
    let a = 0;
    for (let i = 0; i < n; i++) { const [x0, z0] = poly2[i], [x1, z1] = poly2[(i + 1) % n]; a += x0 * z1 - x1 * z0; }
    const ccw = a > 0;
    const vis = [];
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      const [x0, z0] = poly2[i], [x1, z1] = poly2[j];
      const dx = x1 - x0, dz = z1 - z0, len = Math.hypot(dx, dz) || 1;
      const nx = ccw ? dz / len : -dz / len, nz = ccw ? -dx / len : dx / len;
      const v = nz > 0.02 || (Math.abs(nz) <= 0.02 && nx * cosA > 1e-6);
      vis.push(v);
      if (!v) continue;
      const q = [at([x0, y1, z0]), at([x1, y1, z1]), at([x1, y0, z1]), at([x0, y0, z0])];
      fills.push(k.pathOf(q, true));
      edges.push(k.pathOf([at([x0, y0, z0]), at([x1, y0, z1])]));
      if (nz > 0.3) tops.push({ d: k.pathOf(q, true), i, x0, x1, z0, z1 });
      else shadesB[shadeOf(nx, 0)].push(k.pathOf(q, true));
    }
    parts.push(`<path class="iso-fill" d="${fills.join("")}"/>`);
    shadesB.forEach((ds, s) => ds.length && parts.push(`<path class="iso-shade" data-shade="${s}" d="${ds.join("")}"/>`));
    parts.push(`<path class="iso-shade" data-shade="${shadeOf(0, 1)}" d="${k.pathOf(front, true)}"/>`);
    if (topSplit) {
      const groups = {};
      for (const t of tops) { const c = topSplit(t); (groups[c] = groups[c] || []).push(t.d); }
      for (const c in groups) parts.push(`<path class="${c}" d="${groups[c].join("")}"/>`);
    } else if (tops.length) parts.push(`<path class="${topClass}" d="${tops.map((t) => t.d).join("")}"/>`);
    edges.push(k.pathOf(front, true));
    for (let i = 0; i < n; i++) if (vis[i] !== vis[(i + n - 1) % n]) edges.push(k.pathOf([at([poly2[i][0], y1, poly2[i][1]]), at([poly2[i][0], y0, poly2[i][1]])]));
    parts.push(`<path class="iso-line iso-crease" data-tone="faint" d="${tops.map((t) => k.pathOf([at([t.x0, y1, t.z0]), at([t.x1, y1, t.z1])])).join("")}"/>`);
    parts.push(`<path class="iso-line iso-edge" data-tone="${tone}" d="${edges.join("")}"/>`);
    return `<g class="iso-solid ${cls}">${parts.join("")}</g>`;
  }
  // plain box with no rounding: fill, two side shades, top and outline. Cheap for repeated parts.
  function box(x0, y0, z0, x1, y1, z1, { tone = "lo", cls = "" } = {}) {
    const A = (x, y, z) => at([x, y, z]);
    const p = (pts) => k.pathOf(pts, true);
    const top = [A(x0, y0, z1), A(x1, y0, z1), A(x1, y1, z1), A(x0, y1, z1)];
    const fy = [A(x0, y1, z1), A(x1, y1, z1), A(x1, y1, z0), A(x0, y1, z0)];
    const fx = [A(x1, y0, z1), A(x1, y1, z1), A(x1, y1, z0), A(x1, y0, z0)];
    const hull = [A(x0, y0, z1), A(x1, y0, z1), A(x1, y0, z0), A(x1, y1, z0), A(x0, y1, z0), A(x0, y1, z1)];
    return `<g class="iso-solid${cls ? " " + cls : ""}"><path class="iso-fill" d="${p(hull)}"/><path class="iso-shade" data-shade="${shadeOf(0, 1)}" d="${p(fy)}"/><path class="iso-shade" data-shade="${shadeOf(1, 0)}" d="${p(fx)}"/><path class="iso-top" d="${p(top)}"/><path class="iso-line iso-edge" data-tone="${tone}" d="${p(hull)}${k.pathOf([A(x0, y1, z1), A(x1, y1, z1), A(x1, y0, z1)])}${k.pathOf([A(x1, y1, z1), A(x1, y1, z0)])}"/></g>`;
  }
  return { box, at, S, L, D, depth, byDepth, poly, line, halo, text, up, shadeOf, facing, plate, ruler, labelPlate, prismY, sinA, cosA };
}

// screen basis for live scripts
export function basis(P) {
  const O = k.iso([0, 0, 0], P);
  return { O: r4(O), vx: r4(k.axisVector(P, [1, 0, 0])), vy: r4(k.axisVector(P, [0, 1, 0])), vz: r4(k.axisVector(P, [0, 0, 1])) };
}

// Repeated parts: one prototype in <defs>, instances as empty <g data-use> that the page fills by cloning
// (no ids, so mocks can be cloned). expandUses() does the same in Node for the static no-JS image.
export const protoG = (name, inner) => `<g data-proto="${name}">${inner}</g>`;
export const useG = (name, transform, attrs = "") => `<g data-use="${name}"${transform ? ` transform="${transform}"` : ""}${attrs}></g>`;
export function expandUses(svg) {
  const protos = {};
  svg.replace(/<g data-proto="([^"]+)">([\s\S]*?)<\/g><!--\/proto-->/g, (m, n, inner) => { protos[n] = inner; return m; });
  return svg.replace(/<defs class="fg-defs">[\s\S]*?<\/defs>/, "").replace(/<g data-use="([^"]+)"([^>]*)><\/g>/g, (m, n, rest) => `<g${rest}>${protos[n]}</g>`);
}
export const defs = (protos) => `<defs class="fg-defs">${protos.map(([n, inner]) => protoG(n, inner) + "<!--/proto-->").join("")}</defs>`;
export const tr = (v, x) => `translate(${(v[0] * x).toFixed(1)} ${(v[1] * x).toFixed(1)})`;

// shorter path data: relative moves from the 0.1-rounded absolutes, so nothing drifts
const fmt = (v) => { let s = (Math.round(v * 10) / 10).toFixed(1); if (s.endsWith(".0")) s = s.slice(0, -2); if (s.startsWith("0.")) s = s.slice(1); else if (s.startsWith("-0.")) s = "-" + s.slice(2); return s === "-0" ? "0" : s; };
const pair = (a, b) => { const x = fmt(a), y = fmt(b); return x + (y[0] === "-" ? "" : " ") + y; };
export function minD(d) {
  if (/[^MLZmlz0-9.\-\s,e]/.test(d)) return d;
  const toks = d.match(/[MLZmlz]|-?\d*\.?\d+(?:e-?\d+)?/g);
  if (!toks || /[mlz]/.test(d)) return d;
  let out = "", cx = 0, cy = 0, sx = 0, sy = 0, last = "", i = 0;
  while (i < toks.length) {
    const c = toks[i++];
    if (c === "Z") { out += "z"; cx = sx; cy = sy; last = "z"; continue; }
    const x = Math.round(+toks[i++] * 10) / 10, y = Math.round(+toks[i++] * 10) / 10;
    if (c === "M") { out += "m" + pair(x - cx, y - cy); sx = x; sy = y; last = "m"; }
    else { const p = pair(x - cx, y - cy); out += (last === "l" ? (p[0] === "-" ? "" : " ") : "l") + p; last = "l"; }
    cx = x; cy = y;
  }
  return out;
}
// side faces come as one quad per facet; facets that share an edge are one strip, drawn as one polygon
export function mergeQuads(d) {
  if (/[^MLZ0-9.\-\s]/.test(d)) return d;
  const subs = d.split("Z").map((t) => t.trim()).filter(Boolean).map((t) => (t.match(/-?\d*\.?\d+/g) || []).map(Number));
  if (!subs.every((n) => n.length === 8)) return d;
  const q = subs.map((n) => [[n[0], n[1]], [n[2], n[3]], [n[4], n[5]], [n[6], n[7]]]);
  const eq = (a, b) => Math.abs(a[0] - b[0]) < 0.05 && Math.abs(a[1] - b[1]) < 0.05;
  const strips = [];
  for (const [a, b, c, e] of q) {
    const s = strips[strips.length - 1];
    if (s && eq(s.top[s.top.length - 1], a) && eq(s.bot[s.bot.length - 1], e)) { s.top.push(b); s.bot.push(c); }
    else strips.push({ top: [a, b], bot: [e, c] });
  }
  return strips.map((s) => { const p = [...s.top, ...s.bot.reverse()]; return "M" + p.map((v) => v[0].toFixed(1) + " " + v[1].toFixed(1)).join("L") + "Z"; }).join("");
}
export const minify = (svg) => svg.replace(/<path class="iso-shade"([^>]*?) d="([^"]*)"/g, (m, a, d) => `<path class="iso-shade"${a} d="${mergeQuads(d)}"`).replace(/ d="([^"]*)"/g, (m, d) => ` d="${minD(d)}"`);
