"use client";

import { useEffect, useState } from "react";

export type TocItem = { id: string; label: string; children?: TocItem[] };

// "On this page" with scroll-spy. Server-rendered as a plain list of links
// (works without JS); after hydration an IntersectionObserver marks the
// section being read with aria-current.
export function TocList({ items, spy = true }: { items: TocItem[]; spy?: boolean }) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (!spy) return;
    const ids = items.flatMap((i) => [i.id, ...(i.children ?? []).map((c) => c.id)]);
    const els = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (!els.length) return;
    const visible = new Map<string, number>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) visible.set(e.target.id, e.boundingClientRect.top);
          else visible.delete(e.target.id);
        }
        // The topmost heading inside the reading band wins; when none is
        // inside it, keep the last one so the rail never goes blank.
        let best: string | null = null;
        let bestTop = Infinity;
        for (const [id, top] of visible) {
          if (top < bestTop) {
            best = id;
            bestTop = top;
          }
        }
        if (best) setActive(best);
      },
      { rootMargin: "0px 0px -65% 0px", threshold: 0 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [items, spy]);

  return (
    <ol>
      {items.map((item) => {
        const childActive = item.children?.some((c) => c.id === active);
        return (
          <li key={item.id}>
            <a href={`#${item.id}`} aria-current={active === item.id || childActive ? "true" : undefined}>
              {item.label}
            </a>
            {item.children?.length ? (
              <ol>
                {item.children.map((c) => (
                  <li key={c.id}>
                    <a href={`#${c.id}`} aria-current={active === c.id ? "true" : undefined}>
                      {c.label}
                    </a>
                  </li>
                ))}
              </ol>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
