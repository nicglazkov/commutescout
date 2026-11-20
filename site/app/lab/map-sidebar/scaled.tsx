"use client";

import { useLayoutEffect, useRef, useState } from "react";

// Renders a fixed-size mock "screen" (e.g. 1280 x 800) and scales it to
// the width of its column, so every mockup is drawn at real product size.
export function Scaled({
  w,
  h,
  label,
  className = "",
  children,
}: {
  w: number;
  h: number;
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [s, setS] = useState(0.6);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fit = () => setS(el.clientWidth / w);
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [w]);
  return (
    <div
      ref={ref}
      role="img"
      aria-label={label}
      className={`relative w-full overflow-hidden rounded-[var(--cs-radius-md)] border border-cs-line ${className}`}
      style={{ height: h * s }}
    >
      <div
        className="msb-screen absolute left-0 top-0 origin-top-left"
        style={{ width: w, height: h, transform: `scale(${s})` }}
        aria-hidden="true"
        inert
      >
        {children}
      </div>
    </div>
  );
}
