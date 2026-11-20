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
