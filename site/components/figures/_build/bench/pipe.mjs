// Builds the CommuteScout sorting-bench figure as a page fragment.
// node build.mjs  -> writes web-directions/src/parts/figure.html and figure-preview.html
const kit = await import("../kit/iso-kit.mjs");
const FULL = process.env.BENCH_LITE !== "1";
import { defs, useG } from "./common.mjs";
// lighter round parts and slabs: the figure ships under budget, the silhouettes hold at this size
const cap = (n, r) => (FULL ? Math.min(n, r > 10 ? 28 : r > 4 ? 14 : 8) : Math.min(n, r > 10 ? 10 : r > 4 ? 7 : 5));
const k = { ...kit,
  cylinder: (cx, cy, r, z, h, P, steps = 32, bevel = 0) => kit.cylinder(cx, cy, r, z, h, P, cap(steps, r), bevel),
  ring: (cx, cy, r, z, P, steps = 32) => kit.ring(cx, cy, r, z, P, cap(steps, r)),
  knurl: (cx, cy, r, z0, z1, n, P, ...rest) => (FULL ? kit.knurl(cx, cy, r, z0, z1, Math.min(n, 28), P, ...rest) : ""),
  slabOf: (plan, z, h, P, steps = 8, bevel = 0) => kit.slabOf(plan, z, h, P, Math.min(steps, 3), bevel),
};

const W = 960;
const AZ = 58;

// ---------- world ----------
const PLATE = { x: -248, y: -92, w: 440, d: 160, r: 10 };
const PITCH = 40;
const SLOT_X = (i) => -200 + PITCH * i; // 0..4 under hoppers, 5 stamper, 6 gauge, 7 splitter
const BELT_Z = 16;
const CARD = { w: 18, d: 13, h: 1.4 };
const HOPPER_Y = [-72, -46];
// five intake chutes stand for the 53 feeds, grouped by what they publish (generic names, no agencies)
const FEEDS = ["Incident logs", "Closures and roadwork", "Chain controls", "Signs and road weather", "Weather alerts and wildfires"];
const STAMP_X = SLOT_X(5);
const GAUGE = [SLOT_X(6), -38];
const DIAL_R = 15, DIAL_Z = 34, DIAL_TOP = 41;
const SPLIT = [SLOT_X(7), 0];
const FLAGPOLE = [62, -50, 64];
const TRAYS = [
  { name: "map", angle: -50, len: 42 },
  { name: "app", angle: 0, len: 58 },
  { name: "mcp", angle: 50, len: 40 },
];

// fit
const fitPts = [...k.boxCorners(PLATE, -17, 0), [-200, -72, 64], [-90, -72, 64], [FLAGPOLE[0], FLAGPOLE[1], FLAGPOLE[2] + 4], [150, 3, 52]];
let P = k.fitProjection(fitPts, W, 600, { pad: 14, azimuth: AZ });
const ys = fitPts.map((p) => k.iso(p, P)[1]);
const H = Math.ceil(Math.max(...ys) - Math.min(...ys) + 40);
P = k.fitProjection(fitPts, W, H, { pad: 16, azimuth: AZ });

const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);
const poly = (pts, cls, extra = "") => `<path class="${cls}" ${extra}d="${k.pathOf(pts.map(at), true)}"/>`;
const byDepth = (pts) => [...pts].sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P));
const rotRing = (cx, cy, w, d, deg, r = 1.2, steps = 4) => {
  const a = (deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  return k.roundedPlan({ x: -w / 2, y: -d / 2, w, d, r }, steps).map(([x, y]) => [cx + x * c - y * s, cy + x * s + y * c]);
};
const ex = (ring, z, h, bevel = 0) => k.extrude(ring, z, h, P, { convex: true, bevel });
const halo = (plan, z, blur = 6) => `<path class="iso-halo" style="filter:blur(${blur}px)" d="${k.haloOf(plan, z, 0.1, P)}"/>`;
const text = (m, t, size, cls = "", anchor = "middle") => `<text class="iso-face-text ${cls}" transform="${m}" font-size="${size}" text-anchor="${anchor}">${t}</text>`;

// ---------- base ----------
function base() {
  const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -17, 12, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(PLATE, 24))) {
    out.push(S(k.cylinder(x, y, 7, -17, 1.6, P, 22), { tone: "lo" }));
    out.push(S(k.cylinder(x, y, 5.4, -15.4, 3.4, P, 22), { tone: "mid" }));
  }
  out.push(S(k.slabOf(PLATE, -12, 12, P, 8, 1.6), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: "lo" }));
  const screws = k.corners(PLATE, 11);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 16)).join(""), { tone: "lo" }));
  out.push(D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.55 }));
  return out.join("");
}

// ---------- hoppers (intake chutes) ----------
function hopper(i) {
  const cx = SLOT_X(i);
  const plan = { x: cx - 14, y: HOPPER_Y[0], w: 28, d: 26, r: 2 };
  const top = 58;
  const fy = HOPPER_Y[1];
  const out = [];
  out.push(halo(plan, 0, 5));
  out.push(S(k.slabOf(k.insetPlan(plan, -1), 0, 4, P, 3, 0.5), { tone: "lo" })); // plinth
  out.push(S(k.slabOf(plan, 4, top - 4, P, 4, 0.8), { tone: "mid", inner: L(k.sideSeam(plan, 26, P, 4), { tone: "faint" }) }));
  // open top well with a stack of cards
  const well = k.insetPlan(plan, 3);
  out.push(poly(k.roundedPlan(well, 3).map(([x, y]) => [x, y, top]), "cs-well"));
  out.push(L(k.planOutline(well, top, P, 3), { tone: "lo" }));
  for (let s = 0; s < 3; s++) {
    const cz = top - 1.2 - s * 0;
    const c = { x: cx - 9 + s * 0.8, y: HOPPER_Y[0] + 7 + s * 1.2, w: 18, d: 13, r: 1 };
    out.push(L(k.planOutline(c, cz, P, 2), { tone: s === 2 ? "mid" : "lo" }));
  }
  // front face: slot, engraved name, rule, screws
  out.push(poly([[cx - 10, fy, 15.6], [cx + 10, fy, 15.6], [cx + 10, fy, 20], [cx - 10, fy, 20]], "cs-slot"));
  out.push(L(k.pathOf([[cx - 10, fy, 20], [cx + 10, fy, 20]].map(at)), { tone: "mid" }));
  out.push(L(k.pathOf([[cx - 11, fy, 33], [cx + 11, fy, 33]].map(at)), { tone: "faint", free: true }));
  out.push(D([[cx - 11, fy, 52], [cx + 11, fy, 52], [cx - 11, fy, 9], [cx + 11, fy, 9]].map(at), { size: 0.5 }));
  // status lamp on the lid, front right
  out.push(`<g class="cs-lamp">${S(k.cylinder(cx + 9, fy - 4, 2.6, top, 1.6, P, 16), { tone: "mid" })}</g>`);
  // knurled tension knob on the right side
  out.push(S(k.cylinder(cx - 9, fy - 4, 2, top, 2.4, P, 12), { tone: "mid" }));
  out.push(L(k.knurl(cx - 9, fy - 4, 2, top, top + 2.4, 12, P), { tone: "lo" }));
  return out.join("");
}
function lip(i) {
  const cx = SLOT_X(i);
  const plan = { x: cx - 10, y: HOPPER_Y[1], w: 20, d: 32, r: 0.6 };
  const out = [];
  out.push(S(k.slabOf({ x: cx - 3, y: -40, w: 6, d: 24, r: 0.6 }, 0, 14, P, 2), { tone: "lo" })); // bracket
  out.push(S(k.slabOf(plan, 14, 2, P, 2), { tone: "mid" }));
  out.push(L(k.lineOnTop([cx - 7, HOPPER_Y[1]], [cx - 7, HOPPER_Y[1] + 32], 16, P), { tone: "faint" }));
  out.push(L(k.lineOnTop([cx + 7, HOPPER_Y[1]], [cx + 7, HOPPER_Y[1] + 32], 16, P), { tone: "faint" }));
  return out.join("");
}

// ---------- belt ----------
const BELT = { x: -224, y: -13, w: 284, d: 26, r: 7 };
function beltBack() {
  const out = [];
  out.push(halo(k.insetPlan(BELT, -4), 0, 6));
  for (const x of [-210, -130, -50, 30]) {
    out.push(S(k.slabOf({ x: x - 5, y: -15, w: 10, d: 30, r: 1 }, 0, 6, P, 3, 0.4), { tone: "lo" }));
  }
  out.push(S(k.slabOf({ x: -224, y: -16, w: 284, d: 3, r: 0.8 }, 6, 7.5, P, 3, 0.3), { tone: "mid" }));
  // drive housing at the left end
  const motor = { x: -240, y: -16, w: 14, d: 30, r: 2 };
  out.push(S(k.slabOf(motor, 0, 22, P, 4, 0.6), { tone: "mid" }));
  for (let v = 0; v < 4; v++) {
    const z = 6 + v * 3.4;
    out.push(L(k.pathOf([[motor.x + 3, motor.y + motor.d, z], [motor.x + motor.w - 3, motor.y + motor.d, z]].map(at)), { tone: "lo" }));
  }
  out.push(D([[motor.x + 2, motor.y + motor.d, 19.5], [motor.x + motor.w - 2, motor.y + motor.d, 19.5]].map(at), { size: 0.5 }));
  out.push(L(k.ring(motor.x + 7, motor.y + 15, 4, 22, P, 24), { tone: "lo" }));
  out.push(D([at([motor.x + 7, motor.y + 15, 22])], { size: 0.6, tone: "hi" }));
  // belt body
  out.push(S(k.slabOf(BELT, 12, 4, P, 8, 0.6), { tone: "hi", crease: "lo" }));
  for (const y of [-6, 6]) out.push(L(k.lineOnTop([BELT.x + 7, y], [BELT.x + BELT.w - 7, y], BELT_Z, P), { tone: "faint" }));
  out.push(L(k.ring(BELT.x + 7, 0, 3, BELT_Z, P, 16) + k.ring(BELT.x + BELT.w - 7, 0, 3, BELT_Z, P, 16), { tone: "faint" }));
  out.push(D([at([BELT.x + 7, 0, BELT_Z]), at([BELT.x + BELT.w - 7, 0, BELT_Z])], { size: 0.5 }));
  return out.join("");
}
function beltFront() {
  const out = [];
  const rail = { x: -224, y: 13, w: 284, d: 3, r: 0.8 };
  out.push(S(k.slabOf(rail, 6, 7.5, P, 3, 0.3), { tone: "mid" }));
  // drum hubs on the rail face, and a station scale under each slot
  for (const x of [BELT.x + 7, BELT.x + BELT.w - 7]) {
    out.push(L(k.sideRing([x, 16.01, 9.8], 2.6, "y", P, 18), { tone: "lo" }));
    out.push(D([at([x, 16.01, 9.8])], { size: 0.55, tone: "hi" }));
  }
  const ticks = k.sideTicks(-216, 52, 8, 5, 16.01, 13.5, [1.4, 2.8], P, "x");
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  // take-up knob
  out.push(S(k.slabOf({ x: -224, y: 16, w: 4, d: 3, r: 0.6 }, 8, 3, P, 2), { tone: "mid", crease: "none" }));
  out.push(S(k.cylinder(-222, 22, 3.4, 6, 7, P, 22), { tone: "mid" }));
  out.push(L(k.knurl(-222, 22, 3.4, 6, 13, 22, P), { tone: "lo" }));
  return out.join("");
}

// ---------- stamper ----------
const STAMP_REST = 30, STAMP_DOWN = BELT_Z + CARD.h; // head bottom
function stamperBack() {
  const out = [];
  const x = STAMP_X;
  out.push(S(k.cylinder(x, -27, 4.4, 0, 3, P, 24), { tone: "lo" }));
  out.push(S(k.cylinder(x, -27, 2.8, 3, 59, P, 24), { tone: "mid", crease: "none" }));
  out.push(L(k.sideArc(x, -27, 2.8, 30, P, 12), { tone: "faint" }));
  return out.join("");
}
function stamperHead() {
  const x = STAMP_X;
  const out = [];
  out.push(S(k.cylinder(x, 0, 1.8, STAMP_REST + 6, 26, P, 16), { tone: "mid", crease: "none" }));
  const head = { x: x - 8, y: -7, w: 16, d: 14, r: 1.2 };
  out.push(`<g class="cs-ink">${S(k.slabOf(k.insetPlan(head, 1), STAMP_REST, 1.5, P, 3), { tone: "mid", crease: "none" })}</g>`);
  out.push(S(k.slabOf(head, STAMP_REST + 1.5, 4.5, P, 3, 0.5), { tone: "mid" }));
  out.push(D([[head.x + 2, head.y + 2], [head.x + head.w - 2, head.y + 2], [head.x + 2, head.y + head.d - 2], [head.x + head.w - 2, head.y + head.d - 2]].map(([a, b]) => at([a, b, STAMP_REST + 6])), { size: 0.45 }));
  return out.join("");
}
function stamperTop() {
  const x = STAMP_X;
  const out = [];
  out.push(S(k.cylinder(x, 0, 7, 47, 13, P, 32, 0.6), { tone: "mid" }));
  out.push(L(k.sideArc(x, 0, 7, 51, P, 24), { tone: "faint" }));
  out.push(L(k.knurl(x, 0, 7, 53, 58, 48, P), { tone: "lo" }));
  const bar = { x: x - 6, y: -31, w: 12, d: 62, r: 1.5 };
  out.push(S(k.slabOf(bar, 60, 6, P, 4, 0.6), { tone: "mid" }));
  out.push(D([at([x, -27, 66]), at([x, 27, 66])], { size: 0.55 }));
  out.push(L(k.ring(x, -27, 2, 66, P, 14) + k.ring(x, 27, 2, 66, P, 14), { tone: "lo" }));
  out.push(text(k.topMatrix([x + 2.2, -4], 66, P, "y"), "data_as_of", 2.6, "cs-mono", "middle"));
  return out.join("");
}
function stamperFront() {
  const x = STAMP_X;
  return [
    S(k.cylinder(x, 27, 4.4, 0, 3, P, 24), { tone: "lo" }),
    S(k.cylinder(x, 27, 2.8, 3, 57, P, 24), { tone: "mid", crease: "none" }),
    L(k.sideArc(x, 27, 2.8, 30, P, 12), { tone: "faint" }),
  ].join("");
}

// ---------- freshness gauge ----------
const NEEDLE_FROM = -135, NEEDLE_SPAN = 270, STALE_AT = 0.72;
function gaugeBack() {
  const [x, y] = GAUGE;
  const out = [];
  out.push(halo({ x: x - 9, y: y - 9, w: 18, d: 18, r: 9 }, 0, 4));
  out.push(S(k.cylinder(x, y, 8, 0, 3, P, 28, 0.5), { tone: "lo" }));
  out.push(S(k.cylinder(x, y, 4, 3, DIAL_Z - 3, P, 24), { tone: "mid", crease: "none" }));
  out.push(L(k.sideArc(x, y, 4, 16, P, 14), { tone: "faint" }));
  // flag post
  const [fx, fy, fz] = FLAGPOLE;
  out.push(S(k.cylinder(fx, fy, 4, 0, 2.5, P, 20), { tone: "lo" }));
  out.push(S(k.cylinder(fx, fy, 1.5, 2.5, fz - 2.5, P, 14), { tone: "mid", crease: "none" }));
  out.push(S(k.cylinder(fx, fy, 2.2, fz - 1, 2.6, P, 16), { tone: "mid" }));
  // dial
  out.push(S(k.cylinder(x, y, DIAL_R, DIAL_Z, DIAL_TOP - DIAL_Z, P, 48, 0.8), { tone: "hi", crease: "lo" }));
  out.push(L(k.knurl(x, y, DIAL_R, DIAL_TOP - 2.6, DIAL_TOP, 60, P, 0.3), { tone: "lo" }));
  out.push(L(k.sideArc(x, y, DIAL_R, DIAL_TOP - 2.6, P, 40), { tone: "faint" }));
  out.push(L(k.ring(x, y, DIAL_R - 1.8, DIAL_TOP, P, 64), { tone: "lo" }));
  const from = (NEEDLE_FROM * Math.PI) / 180, span = (NEEDLE_SPAN * Math.PI) / 180;
  const tk = k.radialTicks(x, y, DIAL_R - 2.6, 30, 5, DIAL_TOP, [1.2, 2.6], P, from, span);
  out.push(L(tk.minor, { tone: "lo" }), L(tk.major, { tone: "mid" }));
  const arc = (a0, a1, r) => {
    const pts = [];
    for (let s = 0; s <= 24; s++) {
      const a = from + span * (a0 + ((a1 - a0) * s) / 24);
      pts.push(at([x + Math.sin(a) * r, y - Math.cos(a) * r, DIAL_TOP]));
    }
    return k.pathOf(pts);
  };
  out.push(`<path class="cs-arc cs-arc-ok" d="${arc(0, STALE_AT - 0.01, DIAL_R - 6)}"/>`);
  out.push(`<path class="cs-arc cs-arc-stale" d="${arc(STALE_AT + 0.01, 1, DIAL_R - 6)}"/>`);
  // window lug and crown at the back
  out.push(S(k.cylinder(x, y - DIAL_R - 2, 2.2, DIAL_Z + 2, 4, P, 16), { tone: "mid" }));
  return out.join("");
}
const needleD = (frac) => {
  const [x, y] = GAUGE;
  const a = ((NEEDLE_FROM + NEEDLE_SPAN * frac) * Math.PI) / 180;
  return k.pathOf([at([x - Math.sin(a) * 3, y + Math.cos(a) * 3, DIAL_TOP + 0.2]), at([x + Math.sin(a) * (DIAL_R - 3.4), y - Math.cos(a) * (DIAL_R - 3.4), DIAL_TOP + 0.2])]);
};
function gaugeFront() {
  const [x, y] = GAUGE;
  const out = [];
  // reader arm reaching over the belt from the pedestal, and its head
  out.push(S(k.slabOf({ x: x - 2, y: y + 3, w: 4, d: 34, r: 0.8 }, 24, 3, P, 2, 0.3), { tone: "mid" }));
  out.push(S(k.cylinder(x, y, 5, 22, 7, P, 24), { tone: "mid" }));
  const head = { x: x - 6, y: -7, w: 12, d: 12, r: 1.4 };
  out.push(S(k.slabOf(head, 20, 8, P, 3, 0.5), { tone: "mid" }));
  out.push(L(k.sideSeam(head, 23, P, 3), { tone: "faint" }));
  out.push(D([at([head.x + 2.5, head.y + 2.5, 28]), at([head.x + head.w - 2.5, head.y + head.d - 2.5, 28])], { size: 0.45 }));
  out.push(`<g class="cs-eye">${S(k.cylinder(x + 3, 3, 1.4, 28, 1, P, 14), { tone: "mid", crease: "none" })}</g>`);
  out.push(`<path class="iso-line cs-needle" data-tone="lit" data-free="start" d="${needleD(0.2)}" style="stroke-width:1.2"/>`);
  out.push(S(k.cylinder(x, y, 1.6, DIAL_TOP + 0.2, 0.8, P, 14), { tone: "hi" }));
  return out.join("");
}
const flagD = (deg) => {
  const [fx, fy, fz] = FLAGPOLE;
  const a = (deg * Math.PI) / 180;
  const u = [Math.cos(a), Math.sin(a)], v = [-Math.sin(a), Math.cos(a)];
  const pt = (s, t) => at([fx + u[0] * s + v[0] * t, fy + 1.6, fz + u[1] * s + v[1] * t]);
  return k.pathOf([pt(0, 0), pt(15, 0), pt(15, -9), pt(0, -9)], true);
};

// ---------- splitter and outlets ----------
function trayRing(t) {
  const a = (t.angle * Math.PI) / 180;
  const mid = 17 + t.len / 2;
  return rotRing(SPLIT[0] + Math.cos(a) * mid, SPLIT[1] + Math.sin(a) * mid, t.len + 6, 20, t.angle, 1);
}
function tray(t) {
  const a = (t.angle * Math.PI) / 180;
  const out = [];
  out.push(S(ex(trayRing(t), 12.5, 3.5, 0.4), { tone: "mid" }));
  for (const off of [-6, 6]) {
    const p0 = [SPLIT[0] + Math.cos(a) * 22 - Math.sin(a) * off, SPLIT[1] + Math.sin(a) * 22 + Math.cos(a) * off];
    const p1 = [SPLIT[0] + Math.cos(a) * (17 + t.len) - Math.sin(a) * off, SPLIT[1] + Math.sin(a) * (17 + t.len) + Math.cos(a) * off];
    out.push(L(k.lineOnTop(p0, p1, BELT_Z, P), { tone: "faint" }));
  }
  return out.join("");
}
function splitter() {
  const [x, y] = SPLIT;
  const out = [];
  out.push(halo({ x: x - 22, y: y - 22, w: 44, d: 44, r: 22 }, 0, 6));
  out.push(S(k.cylinder(x, y, 22, 0, 10, P, 48, 0.8), { tone: "mid" }));
  out.push(L(k.sideArc(x, y, 22, 5, P, 40), { tone: "faint" }));
  out.push(S(k.cylinder(x, y, 19.5, 10, 6, P, 48, 0.6), { tone: "hi", crease: "lo" }));
  out.push(L(k.ring(x, y, 15, BELT_Z, P, 56), { tone: "faint" }));
  const bolts = [];
  for (let b = 0; b < 12; b++) {
    const a = (b / 12) * Math.PI * 2;
    bolts.push(at([x + Math.cos(a) * 17.2, y + Math.sin(a) * 17.2, BELT_Z]));
  }
  out.push(D(bolts, { size: 0.45 }));
  return out.join("");
}
function mapTable() {
  const plan = { x: 108, y: -88, w: 72, d: 42, r: 2 };
  const out = [halo(plan, 0, 7)];
  for (const [lx, ly] of byDepth(k.corners(plan, 4))) out.push(S(k.slabOf({ x: lx - 2, y: ly - 2, w: 4, d: 4, r: 0.6 }, 0, 10, P, 2), { tone: "lo" }));
  out.push(S(k.slabOf(plan, 10, 6, P, 4, 0.8), { tone: "mid" }));
  const glass = k.insetPlan(plan, 4);
  out.push(`<g class="cs-glass">${poly(k.roundedPlan(glass, 2).map(([a, b]) => [a, b, 16]), "cs-glass-fill")}</g>`);
  out.push(L(k.planOutline(glass, 16, P, 2), { tone: "lo" }));
  const grid = [];
  for (let gx = glass.x + 6; gx < glass.x + glass.w; gx += 6) grid.push(k.lineOnTop([gx, glass.y], [gx, glass.y + glass.d], 16, P));
  for (let gy = glass.y + 6; gy < glass.y + glass.d; gy += 6) grid.push(k.lineOnTop([glass.x, gy], [glass.x + glass.w, gy], 16, P));
  out.push(L(grid.join(""), { tone: "faint" }));
  // roads drawn on the glass
  const roads = [
    [[glass.x, glass.y + 26], [glass.x + 18, glass.y + 21], [glass.x + 34, glass.y + 23], [glass.x + 50, glass.y + 13], [glass.x + glass.w, glass.y + 10]],
    [[glass.x + 26, glass.y], [glass.x + 30, glass.y + 12], [glass.x + 34, glass.y + 23], [glass.x + 40, glass.y + glass.d]],
  ];
  out.push(roads.map((r) => `<path class="cs-road" d="${k.pathOf(r.map(([a, b]) => at([a, b, 16])))}"/>`).join(""));
  const marks = [[glass.x + 18, glass.y + 21], [glass.x + 50, glass.y + 13], [glass.x + 30, glass.y + 12], [glass.x + 56, glass.y + 26], [glass.x + 8, glass.y + 10]];
  out.push(`<g class="cs-mapdots">${marks.map(([a, b]) => `<path class="cs-mapdot" d="${k.ring(a, b, 1.6, 16, P, 14)}"/>`).join("")}</g>`);
  out.push(`<path class="cs-pulse" data-out="map" d=""/>`);
  // engraved name on the front edge
  out.push(text(k.sideMatrix([plan.x + 16, plan.y + plan.d], 11.4, P, "left"), "Map", 3.6, "cs-name"));
  out.push(D([at([plan.x + 3, plan.y + plan.d, 13]), at([plan.x + plan.w - 3, plan.y + plan.d, 13])], { size: 0.45 }));
  return out.join("");
}
const MAP_SPOTS = [[130, -63], [162, -71], [142, -72], [168, -58], [120, -74]];
function phoneDock() {
  const base = { x: 136, y: -12, w: 28, d: 24, r: 3 };
  const out = [halo(base, 0, 5)];
  out.push(S(k.slabOf(base, 0, 9, P, 4, 0.8), { tone: "mid" }));
  out.push(L(k.planOutline(k.insetPlan(base, 2.5), 9, P, 3), { tone: "faint" }));
  out.push(text(k.sideMatrix([base.x + 14, base.y + base.d], 3, P, "left"), "App", 3.6, "cs-name"));
  // cradle back and lip
  out.push(S(k.slabOf({ x: 138, y: -4, w: 24, d: 4, r: 1 }, 9, 12, P, 3, 0.4), { tone: "mid" }));
  out.push(S(k.slabOf({ x: 138, y: 4.4, w: 24, d: 2.4, r: 0.8 }, 9, 3, P, 2), { tone: "mid" }));
  // phone standing in the dock, screen to the viewer
  const phone = { x: 139, y: 0, w: 22, d: 4.2, r: 1.6 };
  out.push(S(k.slabOf(phone, 10, 40, P, 4, 0.5), { tone: "hi", crease: "lo" }));
  const fy = phone.y + phone.d + 0.02;
  const sx0 = 141, sx1 = 159, sz0 = 13, sz1 = 47;
  out.push(poly([[sx0, fy, sz0], [sx1, fy, sz0], [sx1, fy, sz1], [sx0, fy, sz1]], "cs-screen"));
  const scr = (pts) => k.pathOf(pts.map(([a, b]) => at([a, fy, b])));
  out.push(`<path class="cs-road" d="${scr([[sx0, 22], [146, 26], [150, 34], [sx1, 38]])}"/>`);
  out.push(`<path class="cs-road" d="${scr([[152, sz0], [151, 24], [150, 34], [147, sz1]])}"/>`);
  out.push(`<path class="cs-route" d="${scr([[sx0 + 0.6, 22.2], [146, 26], [150, 34], [sx1 - 0.6, 37.8]])}"/>`);
  out.push(`<path class="cs-pulse" data-out="app" d=""/>`);
  out.push(L(scr([[146, 45], [154, 45]]), { tone: "lo", free: true }));
  out.push(`<path class="cs-phonedot" d="${k.sideRing([150, fy, 34], 1.4, "y", P, 14)}"/>`);
  out.push(D([at([150, fy, 11.6])], { size: 0.5 }));
  return out.join("");
}
const APP_SPOT = [150, 4.22, 34];
function terminal() {
  const box = { x: 104, y: 30, w: 46, d: 26, r: 2 };
  const out = [halo(box, 0, 6)];
  out.push(S(k.slabOf(box, 0, 22, P, 4, 0.8), { tone: "mid", inner: L(k.sideSeam(box, 6, P, 4), { tone: "faint" }) }));
  // vents on the +x face
  for (let v = 0; v < 5; v++) {
    const yy = box.y + 6 + v * 3.6;
    out.push(L(k.pathOf([[box.x + box.w, yy, 10], [box.x + box.w, yy, 18]].map(at)), { tone: "lo" }));
  }
  // screen on the top
  const scr = { x: box.x + 5, y: box.y + 4, w: 30, d: 18, r: 1 };
  out.push(poly(k.roundedPlan(scr, 2).map(([a, b]) => [a, b, 22]), "cs-screen"));
  out.push(L(k.planOutline(scr, 22, P, 2), { tone: "lo" }));
  const lines = [0, 1, 2];
  lines.forEach((t, i) => out.push(L(k.lineOnTop([scr.x + 3, scr.y + 4.5 + i * 4.5], [scr.x + 3 + [18, 22, 12][i], scr.y + 4.5 + i * 4.5], 22.02, P), { tone: "lo", free: true })));
  out.push(D([at([box.x + 24, box.y + box.d, 16]), at([box.x + 40, box.y + box.d, 16])], { size: 0.45 }));
  // socket and plug on the front face, cable to the plate
  const fy = box.y + box.d;
  out.push(poly([[box.x + 8, fy + 0.02, 8], [box.x + 18, fy + 0.02, 8], [box.x + 18, fy + 0.02, 15], [box.x + 8, fy + 0.02, 15]], "cs-slot"));
  out.push(S(k.slabOf({ x: box.x + 9.5, y: fy, w: 7, d: 4, r: 1 }, 9, 4.6, P, 2, 0.3), { tone: "mid" }));
  out.push(S(k.slabOf({ x: box.x + 10.5, y: fy + 4, w: 5, d: 3, r: 1.4 }, 9.6, 3.4, P, 4), { tone: "mid" }));
  const cable = [[box.x + 13, fy + 7, 11.3], [box.x + 13, fy + 8.6, 10.2], [box.x + 13, fy + 9.4, 6], [box.x + 13, fy + 9.6, 0.8], [box.x + 3, fy + 9.6, 0.8], [box.x - 14, fy + 6, 0.8]];
  out.push(`<path class="cs-cable" d="${k.pathOf(cable.map(at))}"/>`);
  out.push(`<circle class="iso-wire-end" cx="${at(cable[cable.length - 1])[0].toFixed(1)}" cy="${at(cable[cable.length - 1])[1].toFixed(1)}" r="1.3"/>`);
  out.push(`<g class="cs-led">${S(k.cylinder(box.x + 40, box.y + 6, 1.6, 22, 0.8, P, 14), { tone: "mid", crease: "none" })}</g>`);
  return out.join("");
}

// ---------- dedupe station (added for the final proposal) ----------
// dedupe.py: two records from DIFFERENT feeds, same family, within 120 m, are one event; the
// higher-trust feed's record stays on the belt and the other is pushed off into the bin.
const KICK_X = 20;                       // between the stamper (x 0) and the gauge (x 40)
const BIN = { x: 9, y: 24, w: 24, d: 18, r: 1.6 };
const BIN_Z = 10;
function kickerBack() {
  const out = [];
  // a pedestal behind the belt with a pusher arm that reaches over the back rail
  out.push(halo({ x: KICK_X - 6, y: -36, w: 12, d: 12, r: 2 }, 0, 4));
  out.push(S(k.slabOf({ x: KICK_X - 6, y: -36, w: 12, d: 12, r: 1.4 }, 0, 22, P, 3, 0.5), { tone: "mid", inner: L(k.sideSeam({ x: KICK_X - 6, y: -36, w: 12, d: 12, r: 1.4 }, 8, P, 3), { tone: "faint" }) }));
  out.push(D([at([KICK_X - 4, -24, 18]), at([KICK_X + 4, -24, 18])], { size: 0.45 }));
  return out.join("");
}
function kickerArm() {
  const out = [];
  out.push(S(k.slabOf({ x: KICK_X - 2, y: -30, w: 4, d: 14, r: 0.6 }, 18, 3, P, 2, 0.3), { tone: "mid" }));
  out.push(S(k.slabOf({ x: KICK_X - 8, y: -17, w: 16, d: 3, r: 0.6 }, 17.4, 5, P, 2, 0.3), { tone: "hi", crease: "lo" }));
  return out.join("");
}
function chuteAndBin() {
  const out = [];
  // inclined chute from the belt's front edge down to the bin
  out.push(poly([[KICK_X - 9, 16, 12], [KICK_X + 9, 16, 12], [KICK_X + 9, 25, BIN_Z + 0.2], [KICK_X - 9, 25, BIN_Z + 0.2]], "cs-chute"));
  out.push(L(k.pathOf([[KICK_X - 9, 16, 12], [KICK_X - 9, 25, BIN_Z + 0.2]].map(at)) + k.pathOf([[KICK_X + 9, 16, 12], [KICK_X + 9, 25, BIN_Z + 0.2]].map(at)), { tone: "lo" }));
  out.push(halo(BIN, 0, 4));
  out.push(S(k.slabOf(BIN, 0, BIN_Z, P, 3, 0.5), { tone: "mid" }));
  const well = k.insetPlan(BIN, 2);
  out.push(poly(k.roundedPlan(well, 2).map(([x, y]) => [x, y, BIN_Z]), "cs-well"));
  out.push(L(k.planOutline(well, BIN_Z, P, 2), { tone: "lo" }));
  // one duplicate already in the bin, drawn so the no-JS picture shows the step
  const c = { x: BIN.x + 3, y: BIN.y + 3, w: 18, d: 12, r: 1 };
  out.push(`<path class="cs-dupcard" d="${k.pathOf(k.roundedPlan(c, 2).map(([x, y]) => at([x, y, BIN_Z])), true)}"/>`);
  out.push(L(k.lineOnTop([c.x + 3, c.y + 4], [c.x + 10, c.y + 4], BIN_Z, P) + k.lineOnTop([c.x + 3, c.y + 7], [c.x + 8, c.y + 7], BIN_Z, P), { tone: "lo", free: true }));
  out.push(D([at([BIN.x + 2, BIN.y + BIN.d, 7]), at([BIN.x + BIN.w - 2, BIN.y + BIN.d, 7])], { size: 0.45 }));
  return out.join("");
}

// ---------- cards ----------
function cardArt(angle) {
  const ring = rotRing(0, 0, CARD.w, CARD.d, angle, 1.2, 2);
  const z0 = BELT_Z, z1 = BELT_Z + CARD.h;
  const a = (angle * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  const R = (x, y) => [x * c - y * s, x * s + y * c];
  const out = [];
  out.push(S(ex(ring, z0, CARD.h, 0.3), { tone: "hi", crease: "lo", lit: true }));
  [[-7, -3.4, 7], [-7, -0.6, 4], [-7, 2.2, 6]].forEach(([x0, yy, len]) => out.push(L(k.pathOf([at([...R(x0, yy), z1]), at([...R(x0 + len, yy), z1])]), { tone: "mid", free: true })));
  const stamp = [R(1.6, -4.2), R(7.4, -4.2), R(7.4, 4.2), R(1.6, 4.2)].map(([x, y]) => at([x, y, z1]));
  out.push(`<path class="cs-stamp" d="${k.pathOf(stamp, true)}"/>`);
  out.push(`<path class="cs-stamp-line" d="${k.pathOf([at([...R(2.6, -1), z1]), at([...R(6.4, -1), z1])])}${k.pathOf([at([...R(2.6, 1.4), z1]), at([...R(5.4, 1.4), z1])])}"/>`);
  // stale tab: an orange flag standing on the card's back edge
  const tab = rotRing(0, 0, 5, 1.2, angle, 0.3).map(([x, y]) => {
    const [ox, oy] = R(-4.5, -5.2);
    return [x + ox, y + oy];
  });
  out.push(`<g class="cs-tab">${S(ex(tab, z1, 6, 0), { tone: "mid", crease: "none" })}</g>`);
  return out.join("");
}

// ---------- assemble ----------
const pools = { belt: 9 };
const cardsSvg = Array.from({ length: pools.belt }, (_, i) => `<g class="cs-card" data-card="${i}" style="opacity:0">${useG("p-card")}</g>`).join("");
const copiesSvg = TRAYS.map((t) => `<g class="cs-card cs-copy" data-copy="${t.name}" style="opacity:0">${cardArt(t.angle)}</g>`).join("");

const VX = kit.axisVector(P, [1, 0, 0]);
const shift = (i) => `translate(${(VX[0] * PITCH * i).toFixed(1)} ${(VX[1] * PITCH * i).toFixed(1)})`;
const staticCards = [1, 3, 5, 6].map((i) => `<g transform="translate(${(VX[0] * SLOT_X(i)).toFixed(1)} ${(VX[1] * SLOT_X(i)).toFixed(1)})"${i >= 5 ? ' data-stamped=""' : ""} class="cs-card">${cardArt(0)}</g>`).join("");
const PROTOS = [["p-hop", hopper(0)], ["p-lip", lip(0)], ["p-card", cardArt(0)]];
const hoppers = FEEDS.map((f, i) => `<g class="cs-hopper" data-feed="${i}" tabindex="0" role="button" aria-label="${f}: press to make this feed go stale, press again to bring it back" aria-pressed="false">${useG("p-hop", i ? shift(i) : "")}</g>`).join("");
const lips = [0, 1, 2, 3, 4].map((i) => useG("p-lip", i ? shift(i) : "")).join("");

const body = [
  base(),
  mapTable(),
  hoppers,
  stamperBack(),
  kickerBack(),
  gaugeBack(),
  `<path class="cs-flag" d="${flagD(-84)}"/>`,
  lips,
  beltBack(),
  tray(TRAYS[0]),
  splitter(),
  tray(TRAYS[1]),
  tray(TRAYS[2]),
  `<g class="cs-cards">${cardsSvg}${copiesSvg}</g><g class="cs-static">${staticCards.replace(/class="cs-tab"/g, 'class="cs-tab" style="display:none"')}</g>`,
  `<g class="cs-kick">${kickerArm()}</g>`,
  beltFront(),
  chuteAndBin(),
  `<g class="cs-stamphead">${stamperHead()}</g>`,
  stamperTop(),
  gaugeFront(),
  stamperFront(),
  phoneDock(),
  terminal(),
];
if (process.argv.includes("--sizes")) { ["base","map","hoppers","stB","kickB","gaugeB","flag","lips","beltB","tray0","split","tray1","tray2","cards","kickA","beltF","bin","head","stTop","gaugeF","stF","phone","term"].forEach((n,i)=>console.log(n, body[i].length)); }
const bodyStr = body.join("").replace(/<path class="iso-line iso-bevel"[^>]*\/>/g, "");

// screen basis for the live script
const O = at([0, 0, 0]);
const vx = k.axisVector(P, [1, 0, 0]), vy = k.axisVector(P, [0, 1, 0]), vz = k.axisVector(P, [0, 0, 1]);
const r3 = (a) => a.map((v) => Math.round(v * 10000) / 10000);

const svg = `<svg class="iso-svg csfig-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="How feeds become one live feed"><title>How feeds become one live feed</title><desc>Five intake chutes, one per kind of official feed, drop record cards onto a belt. A press stamps each card with the time its own source gave it. A pusher removes a card when another feed already reported the same event within 120 meters, and it drops into a bin. A gauge compares each card's source time with its feed's stale limit; a stale card still goes out, with an orange flag. A splitter sends the same card to the live map, the phone app and the MCP and REST terminal.</desc>${defs(PROTOS)}${bodyStr}</svg>`;

export const GEOM = {
  O: r3(O), vx: r3(vx), vy: r3(vy), vz: r3(vz),
  pitch: PITCH, slot0: SLOT_X(0), hopperY: HOPPER_Y[1] + 2, stampTravel: STAMP_DOWN - STAMP_REST,
  split: SPLIT, trays: TRAYS.map((t) => ({ name: t.name, angle: t.angle, len: t.len })),
  gauge: GAUGE, dialR: DIAL_R, dialTop: DIAL_TOP, needleFrom: NEEDLE_FROM, needleSpan: NEEDLE_SPAN, staleAt: STALE_AT,
  flag: FLAGPOLE, mapSpots: MAP_SPOTS, appSpot: APP_SPOT, kickX: KICK_X, bin: [BIN.x + BIN.w / 2, BIN.y + BIN.d / 2, BIN_Z],
};
export const VIEW = { W, H };
import { minify as MIN } from "./common.mjs";
export const PIPE = { svg: MIN(svg.replace(/<text class="iso-face-text[^>]*>[^<]*<\/text>/g, "")) };
if (process.argv[1] && process.argv[1].endsWith("pipe.mjs")) console.log("bench svg bytes", PIPE.svg.length);
// station markers for the HTML overlay (percent of the viewBox), used by bench.mjs
export const MARKS = Object.fromEntries(Object.entries({
  feeds: [SLOT_X(2), -60, 46], stamp: [STAMP_X, 0, 52], dedupe: [KICK_X + 2, 34, 14], gauge: [GAUGE[0], GAUGE[1], 44],
  split: [SPLIT[0], SPLIT[1], 22], map: [144, -66, 12], app: [150, -6, 24], api: [127, 44, 32],
}).map(([n, p]) => { const [x, y] = at(p); return [n, [+(x / W * 100).toFixed(1), +(y / H * 100).toFixed(1)]]; }));
