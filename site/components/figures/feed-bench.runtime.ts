// Live behaviour for the sorting bench (feed-bench.tsx). Ported from the approved proposal's
// generators/final/pipe.js. It writes attributes on the server-rendered SVG; React never
// re-renders per frame. Returns a controller the component's chips call, and a cleanup.
import type { BENCH_GEOM } from "./feed-bench.art";

type Geom = typeof BENCH_GEOM;
type Slot = {
  el: SVGGElement;
  feed: number;
  born: number;
  stamped: boolean;
  flagged: boolean;
  read: boolean;
  age: number;
  time: Date | null;
  dup: boolean;
  kick: boolean;
  served?: boolean;
  spot?: number[];
};

export type BenchController = {
  setStale: (feed: number, on: boolean) => void;
  destroy: () => void;
};

const T = 2.6; // one belt cycle, seconds
const MOVE = 0.9; // belt advance inside the cycle
const DWELL = T - MOVE;

export function mountBench(
  root: HTMLElement,
  G: Geom,
  opts: { feedCount: number; initialStale: boolean[]; onReadout: (text: string) => void },
): BenchController {
  const svg = root.querySelector<SVGSVGElement>(".bench-svg");
  if (!svg) return { setStale: () => {}, destroy: () => {} };

  const px = (x: number, y: number, z: number) => [
    G.O[0] + x * G.vx[0] + y * G.vy[0] + z * G.vz[0],
    G.O[1] + x * G.vx[1] + y * G.vy[1] + z * G.vz[1],
  ];
  const mv = (x: number, y: number, z: number) => [x * G.vx[0] + y * G.vy[0] + z * G.vz[0], x * G.vx[1] + y * G.vy[1] + z * G.vz[1]];
  const tr = (x: number, y: number, z: number) => {
    const v = mv(x, y, z);
    return `translate(${v[0].toFixed(2)} ${v[1].toFixed(2)})`;
  };
  const path = (pts: number[][], close = false) =>
    pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join("") + (close ? "Z" : "");
  const topRing = (x: number, y: number, z: number, r: number) => {
    const p: number[][] = [];
    for (let i = 0; i < 28; i++) {
      const a = (i / 28) * Math.PI * 2;
      p.push(px(x + Math.cos(a) * r, y + Math.sin(a) * r, z));
    }
    return path(p, true);
  };
  const faceRing = (x: number, y: number, z: number, r: number) => {
    const p: number[][] = [];
    for (let i = 0; i < 28; i++) {
      const a = (i / 28) * Math.PI * 2;
      p.push(px(x + Math.cos(a) * r, y, z + Math.sin(a) * r));
    }
    return path(p, true);
  };
  const needleD = (frac: number) => {
    const a = ((G.needleFrom + G.needleSpan * frac) * Math.PI) / 180;
    const [x, y] = G.gauge;
    const r = G.dialR - 3.4;
    const z = G.dialTop + 0.2;
    return path([px(x - Math.sin(a) * 3, y + Math.cos(a) * 3, z), px(x + Math.sin(a) * r, y - Math.cos(a) * r, z)]);
  };
  const flagD = (deg: number) => {
    const a = (deg * Math.PI) / 180;
    const f = G.flag;
    const u = [Math.cos(a), Math.sin(a)];
    const v = [-Math.sin(a), Math.cos(a)];
    const pt = (s: number, t: number) => px(f[0] + u[0] * s + v[0] * t, f[1] + 1.6, f[2] + u[1] * s + v[1] * t);
    return path([pt(0, 0), pt(15, 0), pt(15, -9), pt(0, -9)], true);
  };
  const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t);
  const ease = (t: number) => {
    t = clamp01(t);
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  };
  const clock = (d: Date) => {
    let h = d.getHours();
    const m = d.getMinutes();
    const s = d.getSeconds();
    const ap = h < 12 ? "AM" : "PM";
    h = h % 12 || 12;
    return `${h}:${m < 10 ? "0" : ""}${m}:${s < 10 ? "0" : ""}${s} ${ap}`;
  };
  const flagAttr = (el: Element | null, on: boolean | undefined, name = "data-stale") => {
    if (!el) return;
    if (on) el.setAttribute(name, "");
    else el.removeAttribute(name);
  };

  // fill the card pool from the one prototype, then drop the static no-JS cards
  const proto = svg.querySelector('[data-proto="p-card"]');
  svg.querySelectorAll('[data-use="p-card"]').forEach((u) => {
    if (proto) u.innerHTML = proto.innerHTML;
    u.removeAttribute("data-use");
  });
  svg.querySelector(".cs-static")?.remove();

  const kick = svg.querySelector<SVGGElement>(".cs-kick");
  const hoppers = Array.from(svg.querySelectorAll<SVGGElement>(".cs-hopper"));
  const cardEls = Array.from(svg.querySelectorAll<SVGGElement>(".cs-card[data-card]"));
  const copies: Record<string, SVGGElement> = {};
  svg.querySelectorAll<SVGGElement>(".cs-copy").forEach((el) => (copies[el.getAttribute("data-copy") || ""] = el));
  const head = svg.querySelector<SVGGElement>(".cs-stamphead");
  const needle = svg.querySelector<SVGPathElement>(".cs-needle");
  const flag = svg.querySelector<SVGPathElement>(".cs-flag");
  const eye = svg.querySelector(".cs-eye");
  const pulses: Record<string, SVGPathElement> = {};
  svg.querySelectorAll<SVGPathElement>(".cs-pulse").forEach((el) => (pulses[el.getAttribute("data-out") || ""] = el));
  const mapDots = Array.from(svg.querySelectorAll(".cs-mapdot"));
  const phoneDot = svg.querySelector(".cs-phonedot");
  const led = svg.querySelector<SVGGElement>(".cs-led");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)");

  const stale = opts.initialStale.slice();
  const slots: (Slot | null)[] = [null, null, null, null, null, null, null, null];
  const free = cardEls.slice();
  let dropped = 0;
  let cyclesLeft = 9;
  let rr = 0;
  let cycle = 0;
  let t = 0;
  let needleAt = 0;
  let needleGoal = 0;
  let flagAt = -84;
  let flagGoal = -84;
  let mapTurn = 0;
  let seed = 7;
  const rand = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  // an illustrative clock: it never reads the visitor's clock
  const simNow = () => new Date(2026, 0, 1, 18, 0, Math.floor(t + cycle * T));
  const flaggedCount = () => stale.filter(Boolean).length;
  const writeReadout = () => {
    const n = flaggedCount();
    opts.onReadout(`${opts.feedCount} feeds · ${n} stale, still served · ${dropped} duplicate${dropped === 1 ? "" : "s"} dropped`);
  };

  function startCycle() {
    cycle++;
    if (cyclesLeft > 0) cyclesLeft--;
    if (slots[5] && slots[5].kick) {
      slots[5].el.style.opacity = "0";
      free.push(slots[5].el);
      slots[5] = null;
    }
    const out = slots[7];
    if (out) {
      out.el.style.opacity = "0";
      free.push(out.el);
    }
    for (let i = 7; i > 0; i--) slots[i] = slots[i - 1];
    slots[0] = null;
    for (let k = 0; k < 5; k++) {
      const h = (rr + k) % 5;
      if (!slots[h] && free.length) {
        const el = free.shift() as SVGGElement;
        el.removeAttribute("data-stamped");
        el.removeAttribute("data-flagged");
        // every third card repeats an event another feed already sent: the pusher takes it off
        slots[h] = { el, feed: h, born: cycle, stamped: false, flagged: false, read: false, age: 0.1 + rand() * 0.36, time: null, dup: cycle % 3 === 0, kick: false };
        rr = h + 1;
        break;
      }
    }
    for (const key in copies) copies[key].style.opacity = "0";
  }

  // events inside the dwell, run once each per cycle as d passes them
  function dwellEvents(d: number) {
    const s = slots[5];
    if (s && !s.stamped && d >= 0.45) {
      s.stamped = true;
      s.time = simNow();
      s.el.setAttribute("data-stamped", "");
    }
    if (s && s.dup && s.stamped && !s.kick && d >= 0.75) {
      s.kick = true;
      dropped++;
      writeReadout();
    }
    const g = slots[6];
    if (g && !g.read && d >= 0.1) {
      g.read = true;
      needleGoal = stale[g.feed] ? 0.84 + rand() * 0.1 : g.age;
    }
    if (g && !g.flagged && stale[g.feed] && d >= 0.55) {
      g.flagged = true;
      g.el.setAttribute("data-flagged", "");
    }
    flagGoal = g && g.flagged ? 28 : -84;
    if (!g) needleGoal = 0;
    flagAttr(eye, g?.flagged);
    const o = slots[7];
    if (o && !o.served && d >= 1.3) {
      o.served = true;
      const spot = G.mapSpots[mapTurn % G.mapSpots.length];
      const dot = mapDots[mapTurn % mapDots.length];
      mapTurn++;
      flagAttr(dot, o.flagged);
      flagAttr(phoneDot, o.flagged);
      o.spot = spot;
      const term = svg?.querySelector(".cs-term-time");
      if (term && o.time) term.textContent = "as_of " + clock(o.time);
    }
  }

  function place(card: Slot, slot: number, d: number, moving: number) {
    let x = G.slot0 + G.pitch * slot;
    let y = 0;
    let op = 1;
    if (moving < 1) x = G.slot0 + G.pitch * (slot - 1) + G.pitch * ease(moving);
    if (card.born === cycle) {
      x = G.slot0 + G.pitch * slot;
      if (moving < 1) op = 0;
      else {
        const k = clamp01((d - 0.15) / 1.05);
        y = G.hopperY + (0 - G.hopperY) * ease(k);
        op = clamp01(k * 4);
      }
    }
    if (slot === 7 && moving >= 1) op = 1 - clamp01((d - 0.12) / 0.22);
    if (card.kick && slot === 5) {
      const q = ease(clamp01((d - 0.75) / 0.6));
      x = G.slot0 + G.pitch * 5 + (G.kickX - G.slot0 - G.pitch * 5) * q;
      y = G.bin[1] * q;
      card.el.setAttribute("transform", tr(x, y, (G.bin[2] - 16) * q));
      card.el.style.opacity = (1 - clamp01((q - 0.8) / 0.2)).toFixed(3);
      return;
    }
    card.el.setAttribute("transform", tr(x, y, 0));
    card.el.style.opacity = op.toFixed(3);
  }

  function render(dt: number) {
    const moving = t < MOVE ? t / MOVE : 1;
    const d = t < MOVE ? 0 : t - MOVE;
    for (let i = 0; i < 8; i++) {
      const s = slots[i];
      if (s) place(s, i, d, moving);
    }
    // stamper: a calm press, hold, lift
    let press = 0;
    if (moving >= 1 && slots[5]) {
      if (d < 0.15) press = 0;
      else if (d < 0.45) press = ease((d - 0.15) / 0.3);
      else if (d < 0.6) press = 1;
      else press = 1 - ease((d - 0.6) / 0.4);
    }
    head?.setAttribute("transform", tr(0, 0, G.stampTravel * press));
    // pusher: reaches across the belt while a duplicate leaves, then returns
    let pk = 0;
    const s5 = slots[5];
    if (moving >= 1 && s5 && s5.dup) {
      const u = d - 0.62;
      pk = u < 0 ? 0 : u < 0.45 ? ease(u / 0.45) : u < 0.7 ? 1 : 1 - ease((u - 0.7) / 0.5);
    }
    kick?.setAttribute("transform", tr(0, 26 * pk, 0));
    // needle and flag follow with a short time constant (exponential follow)
    const a = dt ? 1 - Math.exp(-dt / 0.16) : 1;
    const b = dt ? 1 - Math.exp(-dt / 0.22) : 1;
    needleAt += (needleGoal - needleAt) * a;
    flagAt += (flagGoal - flagAt) * b;
    needle?.setAttribute("d", needleD(needleAt));
    flag?.setAttribute("d", flagD(flagAt));
    // copies fan out to the outlets
    const o = slots[7];
    for (const tray of G.trays) {
      const el = copies[tray.name];
      if (!el) continue;
      if (!o || moving < 1) {
        el.style.opacity = "0";
        continue;
      }
      const k = clamp01((d - 0.1) / 1.2);
      const dist = (11 + tray.len) * ease(k);
      const ang = (tray.angle * Math.PI) / 180;
      el.setAttribute("transform", tr(G.split[0] + Math.cos(ang) * dist, G.split[1] + Math.sin(ang) * dist, 0));
      el.style.opacity = Math.min(clamp01((d - 0.1) / 0.18), 1 - clamp01((k - 0.82) / 0.18)).toFixed(3);
      flagAttr(el, o.stamped, "data-stamped");
      flagAttr(el, o.flagged, "data-flagged");
    }
    // pulses at the outlets
    const p = o && o.served && moving >= 1 ? clamp01((d - 1.3) / 0.4) : 1;
    const po = p >= 1 ? 0 : (1 - p) * 0.9;
    const st = !!(o && o.flagged);
    if (pulses.map) {
      if (po > 0 && o?.spot) pulses.map.setAttribute("d", topRing(o.spot[0], o.spot[1], 16, 2 + 7 * p));
      pulses.map.style.opacity = po.toFixed(3);
      flagAttr(pulses.map, st);
    }
    if (pulses.app) {
      if (po > 0) pulses.app.setAttribute("d", faceRing(G.appSpot[0], G.appSpot[1], G.appSpot[2], 1.8 + 5 * p));
      pulses.app.style.opacity = po.toFixed(3);
      flagAttr(pulses.app, st);
    }
    if (led) led.style.opacity = po > 0 ? "1" : "0.55";
  }

  function step(dt: number) {
    t += dt;
    while (t >= T) {
      t -= T;
      startCycle();
    }
    if (t >= MOVE) dwellEvents(t - MOVE);
    render(dt);
  }

  function restState() {
    const keep = cyclesLeft;
    for (let n = 0; n < 11; n++) {
      t = 0;
      startCycle();
      dwellEvents(DWELL);
    }
    t = T - 0.001;
    dwellEvents(DWELL);
    needleAt = needleGoal;
    flagAt = flagGoal;
    render(0);
    for (const key in copies) copies[key].style.opacity = "0";
    cyclesLeft = keep;
    dropped = 1;
    writeReadout();
  }

  let frame = 0;
  let last = 0;
  let visible = false;
  function tick(now: number) {
    const dt = last ? Math.min((now - last) / 1000, 1 / 20) : 1 / 60;
    last = now;
    step(dt);
    // a short tour, not an endless loop: the belt runs a few cycles, then rests until someone changes a feed
    frame = visible && !still.matches && cyclesLeft > 0 ? requestAnimationFrame(tick) : 0;
  }
  function run() {
    if (!frame && visible && !still.matches && cyclesLeft > 0) {
      last = 0;
      frame = requestAnimationFrame(tick);
    }
  }

  function setStale(i: number, on: boolean) {
    stale[i] = on;
    flagAttr(hoppers[i], on);
    // records from this feed already past the gauge now go out flagged
    if (on)
      for (let s = 6; s < 8; s++) {
        const c = slots[s];
        if (c && c.feed === i && c.read) {
          c.flagged = true;
          c.el.setAttribute("data-flagged", "");
        }
      }
    const g = slots[6];
    if (on && g && g.feed === i) needleGoal = 0.84 + rand() * 0.1;
    if (!on && g && g.feed === i) {
      needleGoal = g.age;
      g.flagged = false;
      g.el.removeAttribute("data-flagged");
    }
    if (on) rr = i;
    writeReadout();
    cyclesLeft = Math.max(cyclesLeft, 5);
    if (still.matches) {
      flagGoal = g && g.flagged ? 28 : -84;
      needleAt = needleGoal;
      flagAt = flagGoal;
      render(0);
    } else run();
  }

  stale.forEach((on, i) => flagAttr(hoppers[i], on));
  restState();
  root.setAttribute("data-live", "");

  const io = new IntersectionObserver(
    (entries) => {
      visible = entries[entries.length - 1].isIntersecting;
      if (visible) run();
      else if (frame) {
        cancelAnimationFrame(frame);
        frame = 0;
      }
    },
    { rootMargin: "80px 0px" },
  );
  io.observe(svg);
  const onMotion = () => (still.matches ? restState() : run());
  still.addEventListener("change", onMotion);

  return {
    setStale,
    destroy() {
      io.disconnect();
      still.removeEventListener("change", onMotion);
      if (frame) cancelAnimationFrame(frame);
    },
  };
}
