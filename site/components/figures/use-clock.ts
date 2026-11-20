"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "./hooks";

// Motion runs only while a figure is on screen and the reader has not asked for reduced
// motion. Server render and no-JS show the still picture.
export function usePlay<T extends Element>() {
  const ref = useRef<T>(null);
  const reduced = useReducedMotion();
  const inView = useInView(ref, "0px 0px -10% 0px");
  return { ref, play: inView && !reduced };
}

// Simulated seconds, advancing `speed` times faster than real time while `play` is true and
// wrapping at `loop`. Stopped, it holds `still`. Updates about 15 times a second.
export function useClock(play: boolean, speed: number, still: number, loop: number) {
  const [s, setS] = useState(still);
  useEffect(() => {
    if (!play) return;
    const t0 = performance.now();
    let last = 0;
    let raf = 0;
    const step = (now: number) => {
      if (now - last > 66) {
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
