// Build-time generator for d05-art.ts (the isometric system drawing on /lab/diagrams).
// Run from site/: node app/lab/diagrams/_iso/build.mjs
// Uses the anatomy kit already vendored at components/figures/_build/kit (read only).
// Every static path is precomputed here, so the page ships strings and no float math
// runs on the client (no hydration drift). Live parts get screen anchors.
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import * as K from "../../../../components/figures/_build/kit/iso-kit.mjs";

const AZ = 58;
const r1 = (v) => Math.round(v * 10) / 10;
const pt = (p, P) => K.iso(p, P).map(r1);
const seg = (a, b, P) => K.segment(a, b, P);
const poly = (list, P) => K.pathOf(list.map((p) => K.iso(p, P)));
const face = (list, P) => K.pathOf(list.map((p) => K.iso(p, P)), true);
const S = (paths, o = {}) => K.solidSvg(paths, { crease: "faint", ...o });
const L = (d, tone = "lo", o = {}) => K.lineSvg(d, { tone, ...o });
const D = (points, tone = "mid", size = 0.55) => K.dotsSvg(points, { tone, size });
const ringOnFront = (cx, y, cz, r, P) => K.sideRing([cx, y, cz], r, "y", P, 16);

// ---- lanes (same order as option 1): a unit in the rack, a blade in the server
export const KINDS = ["incident", "closure", "chain", "fire", "weather", "neutral"];

// ---------- parts ----------
// Each builder draws at fixed world coordinates and returns { svg, bounds, anchors }.

function feet(plan, z, h, P, r = 3.2, inset = 7) {
  return K.corners(plan, inset).map(([x, y]) => S(K.cylinder(x, y, r, z, h, P, 16), { tone: "lo" })).join("");
}
function screws(points, P, size = 0.6) {
  return D(K.pointsAt(points, P), "mid", size);
}

const RACK = { x: 0, y: 0, w: 92, d: 72 };
const UNIT_Z = (i) => 16 + i * 26; // bottom unit is i = 0 (cameras), top is i = 5 (patrol)
function rack(P) {
  const out = [];
  const plinth = { ...RACK, r: 2 };
  out.push(feet(plinth, 0, 4, P));
  out.push(S(K.slabOf(plinth, 4, 9, P, 3, 0.8), { tone: "lo" }));
  out.push(L(K.sideSeam(K.insetPlan(plinth, 0), 8.5, P, 3), "faint"));
  // back posts
  for (const x of [0, 88]) out.push(S(K.slabOf({ x, y: 0, w: 4, d: 4, r: 0.5 }, 13, 165, P, 2), { tone: "mid" }));
  const anchors = { leds: [], ports: [] };
  for (let i = 0; i < 6; i++) {
    const z0 = UNIT_Z(i);
    const unit = { x: 4, y: 3, w: 84, d: 64, r: 1.2 };
    let inner = "";
    const fy = 67;
    // vent slots, drive bay, ears
    for (let j = 0; j < 9; j++) inner += L(seg([22 + j * 3.4, fy, z0 + 5], [22 + j * 3.4, fy, z0 + 17], P), "faint");
    inner += L(face([[58, fy, z0 + 5], [80, fy, z0 + 5], [80, fy, z0 + 17], [58, fy, z0 + 17]], P), "lo");
    inner += L(seg([62, fy, z0 + 11], [76, fy, z0 + 11], P), "faint");
    out.push(S(K.slabOf(unit, z0, 22, P, 2, 0.6), { tone: "mid", inner }));
    out.push(screws([[8, fy, z0 + 6], [8, fy, z0 + 16]], P));
    out.push(L(ringOnFront(14, fy, z0 + 11, 2.6, P), "lo"));
    anchors.leds.push(pt([14, fy, z0 + 11], P));
    // network port on the right face, one per unit at its own depth
    const py = 14 + (5 - i) * 7;
    out.push(L(face([[88, py - 2.5, z0 + 8], [88, py + 2.5, z0 + 8], [88, py + 2.5, z0 + 14], [88, py - 2.5, z0 + 14]], P), "lo"));
    anchors.ports.push([88, py, z0 + 11]);
  }
  // front posts with rack holes
  for (const x of [0, 88]) {
    out.push(S(K.slabOf({ x, y: 66, w: 4, d: 4, r: 0.5 }, 13, 165, P, 2), { tone: "mid" }));
  }
  const holes = [];
  for (let z = 20; z < 172; z += 13) holes.push([2, 70, z], [90, 70, z]);
  out.push(D(K.pointsAt(holes, P), "lo", 0.5));
  // top cap with a label plate
  const cap = { ...RACK, r: 2 };
  out.push(S(K.slabOf(cap, 178, 7, P, 3, 0.8), { tone: "mid" }));
  const plate = { x: 22, y: 22, w: 48, d: 28, r: 1.5 };
  out.push(S(K.slabOf(plate, 185, 0.8, P, 3), { tone: "lo", crease: "none", flat: true }));
  for (let k = 0; k < 3; k++) out.push(L(K.lineOnTop([28, 30 + k * 6], [k === 2 ? 50 : 64, 30 + k * 6], 185.8, P), "faint", { free: true }));
  out.push(screws(K.corners(plate, 3).map(([x, y]) => [x, y, 185.8]), P, 0.5));
  out.push(screws(K.corners(cap, 5).map(([x, y]) => [x, y, 185]), P, 0.55));
  return { svg: out.join(""), anchors, top: pt([46, 36, 185], P), bounds: K.boxCorners(RACK, 0, 186) };
}

const APP = { x: 170, y: 10, w: 210, d: 80 };
const BLADE_X = (j) => 178 + j * 24;
const GAUGE = { z0: 20, z1: 64 };
function app(P) {
  const out = [];
  const body = { ...APP, r: 2.5 };
  out.push(feet(body, 0, 4, P, 3.6, 9));
  const fy = APP.y + APP.d; // 90
  let inner = "";
  // right-hand panel on the front: vent slots
  for (let z = 30; z <= 54; z += 4) inner += L(seg([334, fy, z], [366, fy, z], P), "faint");
  // right face: two ports
  inner += L(face([[380, 46, 36], [380, 56, 36], [380, 56, 44], [380, 46, 44]], P), "lo");
  inner += L(face([[380, 70, 16], [380, 80, 16], [380, 80, 24], [380, 70, 24]], P), "lo");
  out.push(S(K.slabOf(body, 4, 82, P, 3, 1), { tone: "mid", inner }));
  // lid: seam, vents, screws, label plate
  const top = 86;
  out.push(L(K.planOutline(K.insetPlan(body, 5), top, P, 3), "faint"));
  out.push(D(K.dotGrid(268, 22, 16, 6, 6, top, P), "lo", 0.55));
  out.push(screws(K.corners(body, 9).map(([x, y]) => [x, y, top]), P));
  const plate = { x: 186, y: 22, w: 64, d: 34, r: 1.5 };
  out.push(S(K.slabOf(plate, top, 0.8, P, 3), { tone: "lo", crease: "none", flat: true }));
  for (let k = 0; k < 3; k++) out.push(L(K.lineOnTop([193, 31 + k * 7], [k === 2 ? 222 : 243, 31 + k * 7], top + 0.8, P), "faint", { free: true }));
  out.push(screws(K.corners(plate, 3).map(([x, y]) => [x, y, top + 0.8]), P, 0.5));
  // blades: one held copy per feed
  const anchors = { leds: [], gauges: [], build: null, port: [380, 51, 40], apiPort: [380, 75, 20] };
  for (let j = 0; j < 6; j++) {
    const x = BLADE_X(j);
    const blade = { x, y: fy - 4, w: 20, d: 7, r: 1 };
    const by = fy + 3;
    let bi = "";
    bi += `<path class="dg-track" d="${seg([x + 10, by, GAUGE.z0], [x + 10, by, GAUGE.z1], P)}"/>`;
    bi += L(seg([x + 6, by, (GAUGE.z0 + GAUGE.z1) / 2], [x + 14, by, (GAUGE.z0 + GAUGE.z1) / 2], P), "mid");
    bi += L(seg([x + 7, by, GAUGE.z0], [x + 13, by, GAUGE.z0], P), "lo");
    bi += L(seg([x + 4, by, 12.5], [x + 16, by, 12.5], P), "lo");
    out.push(S(K.slabOf(blade, 8, 72, P, 2, 0.5), { tone: "mid", inner: bi }));
    out.push(L(ringOnFront(x + 10, by, 72, 2.2, P), "lo"));
    anchors.leds.push(pt([x + 10, by, 72], P));
    anchors.gauges.push([pt([x + 10, by, GAUGE.z0], P), pt([x + 10, by, GAUGE.z1], P)]);
  }
  // build lamp and power ring on the panel
  out.push(L(ringOnFront(350, fy, 68, 3.2, P), "lo"));
  anchors.build = pt([350, fy, 68], P);
  out.push(L(ringOnFront(350, fy, 18, 4.5, P), "mid"));
  out.push(L(seg([350, fy, 16], [350, fy, 20.5], P), "mid"));
  return { svg: out.join(""), anchors, top: pt([300, 50, top], P), bounds: K.boxCorners(APP, 0, 86) };
}

const BUCKET = { x: 440, y: 10, w: 96, d: 80 };
const SLED_Z = [58, 37, 16]; // live (top), signs, cameras
function bucket(P) {
  const out = [];
  const body = { ...BUCKET, r: 2.5 };
  out.push(feet(body, 0, 4, P, 3.4, 8));
  const fy = BUCKET.y + BUCKET.d;
  let inner = "";
  inner += L(face([[536, 46, 36], [536, 56, 36], [536, 56, 44], [536, 46, 44]], P), "lo");
  out.push(S(K.slabOf(body, 4, 76, P, 3, 1), { tone: "mid", inner }));
  const top = 80;
  out.push(L(K.planOutline(K.insetPlan(body, 5), top, P, 3), "faint"));
  for (let k = 0; k < 7; k++) out.push(L(K.lineOnTop([458, 22 + k * 8], [518, 22 + k * 8], top, P), "faint"));
  out.push(screws(K.corners(body, 8).map(([x, y]) => [x, y, top]), P));
  const anchors = { leds: [], sleds: [], port: [536, 51, 40] };
  SLED_Z.forEach((z0, k) => {
    const sled = { x: 446, y: fy - 4, w: 84, d: 7, r: 1 };
    const by = fy + 3;
    let si = "";
    si += L(seg([488, by, z0 + 8], [520, by, z0 + 8], P), "lo");
    si += L(seg([488, by, z0 + 5], [488, by, z0 + 11], P), "lo");
    si += L(seg([520, by, z0 + 5], [520, by, z0 + 11], P), "lo");
    out.push(S(K.slabOf(sled, z0, 16, P, 2, 0.5), { tone: k === 0 ? "hi" : "mid", lit: k === 0, inner: si }));
    out.push(screws([[452, by, z0 + 8]], P, 0.5));
    out.push(L(ringOnFront(462, by, z0 + 8, 2.2, P), "lo"));
    anchors.leds.push(pt([462, by, z0 + 8], P));
    anchors.sleds.push(pt([530, by, z0 + 8], P));
  });
  return { svg: out.join(""), anchors, top: pt([488, 50, top], P), bounds: K.boxCorners(BUCKET, 0, 80) };
}

const EDGE = { x: 584, y: 22, w: 76, d: 56 };
function edge(P) {
  const out = [];
  const body = { ...EDGE, r: 2 };
  out.push(feet(body, 0, 3, P, 2.8, 7));
  const fy = EDGE.y + EDGE.d;
  let inner = "";
  for (let x = 606; x <= 650; x += 4) inner += L(seg([x, fy, 10], [x, fy, 24], P), "faint");
  inner += L(face([[660, 45, 14], [660, 55, 14], [660, 55, 22], [660, 45, 22]], P), "lo");
  out.push(S(K.slabOf(body, 3, 31, P, 3, 0.8), { tone: "mid", inner }));
  const top = 34;
  // cooling fins
  for (let k = 0; k < 8; k++) out.push(S(K.slabOf({ x: 590 + k * 8.6, y: 28, w: 3, d: 44, r: 0.6 }, top, 8, P, 2), { tone: "mid" }));
  out.push(L(ringOnFront(594, fy, 17, 2.2, P), "lo"));
  out.push(screws([[588, fy, 8], [588, fy, 28], [656, fy, 8], [656, fy, 28]], P, 0.5));
  return { svg: out.join(""), anchors: { led: pt([594, fy, 17], P), port: [660, 50, 18], front: pt([622, fy, 3], P) }, top: pt([622, 50, 42], P), bounds: K.boxCorners(EDGE, 0, 42) };
}

const MON = { x: 690, y: 50, w: 150, d: 8 };
const SCREEN = { x0: 698, x1: 832, z0: 44, z1: 126 };
const mapAt = (u, v) => [SCREEN.x0 + u * (SCREEN.x1 - SCREEN.x0), MON.y + MON.d, SCREEN.z0 + v * (SCREEN.z1 - SCREEN.z0)];
function monitor(P) {
  const out = [];
  out.push(S(K.slabOf({ x: 726, y: 22, w: 78, d: 44, r: 10 }, 0, 4, P, 6, 0.8), { tone: "mid" }));
  out.push(S(K.slabOf({ x: 759, y: 40, w: 12, d: 9, r: 1 }, 4, 40, P, 2), { tone: "mid" }));
  out.push(S(K.slabOf({ ...MON, r: 2 }, 36, 96, P, 3, 0.8), { tone: "mid" }));
  const fy = MON.y + MON.d;
  out.push(`<path class="dg-screen" d="${face([[SCREEN.x0, fy, SCREEN.z0], [SCREEN.x1, fy, SCREEN.z0], [SCREEN.x1, fy, SCREEN.z1], [SCREEN.x0, fy, SCREEN.z1]], P)}"/>`);
  out.push(L(face([[SCREEN.x0, fy, SCREEN.z0], [SCREEN.x1, fy, SCREEN.z0], [SCREEN.x1, fy, SCREEN.z1], [SCREEN.x0, fy, SCREEN.z1]], P), "lo"));
  // a generic road map, drawn in the plane of the screen
  const roads = [
    [[0, 0.22], [0.3, 0.3], [0.55, 0.52], [1, 0.6]],
    [[0.18, 0], [0.24, 0.4], [0.36, 0.78], [0.42, 1]],
    [[0.62, 0], [0.66, 0.3], [0.8, 0.62], [0.86, 1]],
    [[0, 0.82], [0.4, 0.76], [1, 0.88]],
  ];
  for (const r of roads) out.push(`<path class="dg-road" d="${poly(r.map(([u, v]) => mapAt(u, v)), P)}"/>`);
  // "Data as of" chip, top left of the screen
  out.push(`<path class="dg-chip" d="${face([mapAt(0.04, 0.9), mapAt(0.36, 0.9), mapAt(0.36, 0.97), mapAt(0.04, 0.97)], P)}"/>`);
  const pins = [[0.27, 0.36], [0.6, 0.53], [0.79, 0.6], [0.37, 0.77], [0.66, 0.24]].map(([u, v]) => pt(mapAt(u, v), P));
  const fresh = pt(mapAt(0.48, 0.47), P);
  const chipDot = pt(mapAt(0.07, 0.935), P);
  return { svg: out.join(""), anchors: { pins, fresh, chipDot, front: pt([772, 66, 2], P) }, top: pt([765, 54, 132], P), bounds: K.boxCorners({ x: 690, y: 22, w: 150, d: 44 }, 0, 132) };
}

const LAP = { x: 150, y: 172, w: 104, d: 66 };
function laptop(P) {
  const out = [];
  // lid (behind the base) with a terminal on its screen
  out.push(S(K.slabOf({ x: LAP.x, y: LAP.y - 4, w: LAP.w, d: 4, r: 1.5 }, 5, 66, P, 2, 0.5), { tone: "mid" }));
  const fy = LAP.y;
  out.push(`<path class="dg-screen" d="${face([[LAP.x + 6, fy, 11], [LAP.x + 98, fy, 11], [LAP.x + 98, fy, 66], [LAP.x + 6, fy, 66]], P)}"/>`);
  const lines = [];
  for (let k = 0; k < 5; k++) {
    const z = 58 - k * 8;
    const len = [62, 48, 70, 40, 54][k];
    lines.push(`<path class="dg-term" d="${seg([LAP.x + 12, fy, z], [LAP.x + 12 + len, fy, z], P)}"/>`);
  }
  out.push(lines.join(""));
  // base with keys and trackpad
  const base = { ...LAP, r: 3 };
  out.push(S(K.slabOf(base, 0, 5, P, 3, 0.6), { tone: "mid" }));
  const keys = [];
  for (let r = 0; r < 4; r++) for (let c = 0; c < 12; c++) keys.push(K.planOutline({ x: LAP.x + 8 + c * 7.4, y: LAP.y + 6 + r * 7, w: 5.6, d: 5.2, r: 0.8 }, 5, P, 2));
  out.push(L(keys.join(""), "faint"));
  out.push(L(K.planOutline({ x: LAP.x + 36, y: LAP.y + 40, w: 32, d: 18, r: 2 }, 5, P, 3), "lo"));
  const cursor = pt([LAP.x + 12, fy, 18], P);
  return { svg: out.join(""), anchors: { cursor, termTop: pt([LAP.x + 12, fy, 58], P), front: pt([LAP.x + 52, LAP.y + LAP.d, 0], P), port: [LAP.x + LAP.w, LAP.y + 30, 2.5], termStep: [r1(K.iso([0, 0, -8], P)[0] - K.iso([0, 0, 0], P)[0]), r1(K.iso([0, 0, -8], P)[1] - K.iso([0, 0, 0], P)[1])] }, top: pt([LAP.x + 52, LAP.y - 2, 71], P), bounds: K.boxCorners({ x: LAP.x, y: LAP.y - 4, w: LAP.w, d: LAP.d + 4 }, 0, 72) };
}

// ---- cables, routed on the base: out of a port, down to the plate, along it
function cable(points, P) {
  return K.pathOf(points.map((p) => K.iso(p, P)));
}
const flatPts = (points, P) => points.map((p) => pt(p, P));

// ---------- the desk drawing ----------
function desk() {
  const plate = { x: -24, y: -22, w: 888, d: 278, r: 8 };
  const bounds = [...K.boxCorners(plate, -16, 0), [46, 36, 186], [765, 54, 132]];
  const W = 820;
  const H = 500;
  const P = K.fitProjection(bounds, W, H, { pad: 6, azimuth: AZ, headroom: 48 });
  const out = [];
  // base plate on feet
  out.push(feet(plate, -16, 6, P, 7, 26));
  out.push(`<path class="iso-halo" d="${K.haloOf(plate, -16, 16, P)}"/>`);
  out.push(S(K.slabOf(plate, -10, 10, P, 6, 1.2), { tone: "lo" }));
  out.push(L(K.planOutline(K.insetPlan(plate, 7), 0, P, 6), "faint"));
  out.push(screws(K.corners(plate, 14).map(([x, y]) => [x, y, 0]), P));
  // zone grooves: agencies | our server and storage | delivery
  out.push(L(K.lineOnTop([140, -15], [140, 249], 0, P), "faint"));
  out.push(L(K.lineOnTop([566, -15], [566, 249], 0, P), "faint"));
  // ruler along the front edge: one tick per 10 units
  const ticks = K.topTicks(-10, 850, 10, 5, 249, 0, [2.5, 5], P, "x");
  out.push(L(ticks.minor, "faint"), L(ticks.major, "lo"));

  const R = rack(P);
  out.push(`<g data-part="rack">${R.svg}</g>`);
  // six cables from the rack to the server, bundled under a clamp
  const feedCables = R.anchors.ports.map(([x, y, z], i) => {
    const dx = 100 + i * 2.4;
    return [[x, y, z], [dx, y, z], [dx, y, 0.6], [APP.x, y, 0.6]];
  });
  out.push(`<g class="dg-cables">${feedCables.map((c) => L(cable(c, P), "mid")).join("")}</g>`);
  const clamp = { x: 128, y: 6, w: 7, d: 56, r: 1 };
  out.push(S(K.slabOf(clamp, 0, 3, P, 2), { tone: "mid" }));
  out.push(screws([[131.5, 9, 3], [131.5, 59, 3]], P, 0.5));

  const A = app(P);
  out.push(`<g data-part="app">${A.svg}</g>`);
  const up = [A.anchors.port, [394, 51, 40], [394, 51, 0.6], [BUCKET.x, 51, 0.6]];
  out.push(L(cable(up, P), "mid"));
  const B = bucket(P);
  out.push(`<g data-part="bucket">${B.svg}</g>`);
  const toEdge = [B.anchors.port, [552, 51, 40], [552, 51, 0.6], [EDGE.x, 51, 0.6]];
  out.push(L(cable(toEdge, P), "mid"));
  const E = edge(P);
  out.push(`<g data-part="edge">${E.svg}</g>`);
  const toMon = [E.anchors.port, [672, 50, 18], [672, 50, 0.6], [726, 50, 0.6]];
  out.push(L(cable(toMon, P), "mid"));
  const M = monitor(P);
  out.push(`<g data-part="monitor">${M.svg}</g>`);
  const T = laptop(P);
  out.push(`<g data-part="laptop">${T.svg}</g>`);
  const api = [A.anchors.apiPort, [396, 75, 20], [396, 75, 0.6], [396, LAP.y + 30, 0.6], [LAP.x + LAP.w, LAP.y + 30, 0.6]];
  out.push(L(cable(api, P), "mid"));

  return {
    w: W,
    h: H,
    art: out.join(""),
    rack: { ...R.anchors, ports: undefined, top: R.top },
    app: { leds: A.anchors.leds, gauges: A.anchors.gauges, build: A.anchors.build, top: A.top },
    bucket: { leds: B.anchors.leds, sleds: B.anchors.sleds, top: B.top },
    edge: { led: E.anchors.led, front: E.anchors.front, top: E.top },
    monitor: { ...M.anchors, top: M.top },
    laptop: { ...T.anchors, top: T.top },
    paths: {
      feeds: feedCables.map((c) => flatPts(c, P)),
      upload: flatPts(up, P),
      toEdge: flatPts(toEdge, P),
      toMap: flatPts(toMon, P),
      api: flatPts(api, P),
    },
  };
}

// ---------- phone: each part on its own, at a scale where its details read ----------
function single(build, extra, W, H, pad = 8) {
  const probe = { origin: [0, 0], scale: 1, azimuth: AZ, elevation: 30 };
  const first = build(probe);
  const P = K.fitProjection([...first.bounds, ...extra], W, H, { pad, azimuth: AZ });
  const part = build(P);
  return { w: W, h: H, art: part.svg, anchors: part.anchors, top: part.top };
}
function phone() {
  return {
    rack: single(rack, [], 150, 190),
    app: single(app, [], 300, 170),
    bucket: single(bucket, [], 170, 150),
    edge: single(edge, [], 150, 90),
    monitor: single(monitor, [], 190, 160),
    laptop: single(laptop, [], 180, 130),
  };
}

const art = { desk: desk(), phone: phone() };
const file = fileURLToPath(new URL("../d05-art.ts", import.meta.url));
writeFileSync(
  file,
  `// Generated by app/lab/diagrams/_iso/build.mjs from the anatomy kit. Do not edit by hand.\n` +

    `export const ART = ${JSON.stringify(art)} as const;\n`,
);
console.log("wrote", file, Math.round(JSON.stringify(art).length / 1024), "KB");
