"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "@/components/figures/hooks";

// Motion runs only while a figure is on screen and the reader has not asked for
// reduced motion. Server render and no-JS show the still picture.
export function usePlay<T extends Element>() {
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();
  const inView = useInView(ref, "0px 0px -10% 0px");
  return { ref, play: inView && !reduced };
}

// A loop position 0..1 that advances only while `play` is true (about 12 updates a
// second, enough for a calm sweep). Stopped, it holds `still`, the frame the static
// picture shows.
export function useLoop(play: boolean, seconds: number, still = 1) {
  const [t, setT] = useState(still);
  useEffect(() => {
    if (!play) return;
    const t0 = performance.now();
    let last = 0;
    let raf = 0;
    const step = (now: number) => {
      if (now - last > 80) {
        last = now;
        setT((((now - t0) / 1000) % seconds) / seconds);
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [play, seconds]);
  return play ? t : still;
}

// Simulated seconds, advancing `speed` times faster than real time while `play` is true
// and wrapping at `loop`. Stopped, it holds `still`. Updates about 12 times a second.
export function useClock(play: boolean, speed: number, still: number, loop: number) {
  const [s, setS] = useState(still);
  useEffect(() => {
    if (!play) return;
    const t0 = performance.now();
    let last = 0;
    let raf = 0;
    const step = (now: number) => {
      if (now - last > 80) {
        last = now;
        setS((still + ((now - t0) / 1000) * speed) % loop);
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [play, speed, still, loop]);
  return play ? s : still;
}

// A point part way along a polyline of screen points.
export function along(points: readonly (readonly number[])[], p: number): [number, number] {
  const seg: number[] = [];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const d = Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
    seg.push(d);
    total += d;
  }
  let want = Math.max(0, Math.min(1, p)) * total;
  for (let i = 1; i < points.length; i++) {
    if (want <= seg[i - 1] || i === points.length - 1) {
      const f = seg[i - 1] ? Math.min(1, want / seg[i - 1]) : 0;
      return [points[i - 1][0] + (points[i][0] - points[i - 1][0]) * f, points[i - 1][1] + (points[i][1] - points[i - 1][1]) * f];
    }
    want -= seg[i - 1];
  }
  return [points[0][0], points[0][1]];
}
