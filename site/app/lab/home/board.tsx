import type { ReactNode } from "react";
import Link from "next/link";

// Shared pieces for the lab brainstorm boards (local only). Every option gets
// a number, a short name, a one-line idea and its trade-off, then the mockup
// rendered at real size.

export function BoardHeader({
  title,
  intro,
  children,
}: {
  title: string;
  intro: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="cs-container pt-12 pb-10">
      <p className="text-sm text-cs-ink-3">
        <Link href="/lab" className="cs-link">
          Lab
        </Link>{" "}
        / local preview only, not part of the site
      </p>
      <h1 className="cs-display mt-3">{title}</h1>
      <div className="cs-lede mt-5 max-w-[46rem]">{intro}</div>
      {children}
    </header>
  );
}

export function Recommend({ items }: { items: { section: string; pick: string; why: ReactNode }[] }) {
  return (
    <div className="mt-8 grid gap-px overflow-hidden rounded-[var(--cs-radius-lg)] border border-cs-accent/40 bg-cs-accent/30 md:grid-cols-2">
      {items.map((r) => (
        <div key={r.section} className="bg-cs-surface p-5">
          <p className="cs-eyebrow text-cs-accent">Recommended · {r.section}</p>
          <p className="mt-2 text-lg font-semibold tracking-[-0.01em] text-cs-ink">{r.pick}</p>
          <p className="mt-1.5 text-[0.9375rem] leading-relaxed text-cs-ink-2">{r.why}</p>
        </div>
      ))}
    </div>
  );
}

export function SectionHead({ id, letter, title, note }: { id: string; letter: string; title: string; note: ReactNode }) {
  return (
    <div id={id} className="cs-container scroll-mt-20 border-t border-cs-line-strong pt-14 pb-4">
      <p className="cs-eyebrow">Section {letter}</p>
      <h2 className="cs-h2 mt-2">{title}</h2>
      <div className="mt-3 max-w-[46rem] text-cs-ink-2">{note}</div>
    </div>
  );
}

export function Option({
  n,
  name,
  idea,
  tradeoff,
  pick,
  children,
  bleed,
}: {
  n: string;
  name: string;
  idea: ReactNode;
  tradeoff: ReactNode;
  pick?: boolean;
  children: ReactNode;
  /** Render the mockup outside the container (for full hero rows). */
  bleed?: boolean;
}) {
  return (
    <article className="border-t border-cs-line py-12" aria-labelledby={`opt-${n}`}>
      <div className="cs-container grid gap-3 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-4">
          <p className="cs-data text-sm text-cs-ink-3">
            {n}
            {pick && (
              <span className="ml-2 rounded-[var(--cs-radius-sm)] bg-cs-accent px-1.5 py-0.5 font-sans text-[0.6875rem] font-semibold uppercase tracking-[0.06em] text-cs-accent-ink">
                Recommended
              </span>
            )}
          </p>
          <h3 id={`opt-${n}`} className="mt-1 text-xl font-semibold tracking-[-0.015em] text-cs-ink">
            {name}
          </h3>
        </div>
        <div className="grid gap-2 text-[0.9375rem] leading-relaxed lg:col-span-8 lg:grid-cols-2 lg:gap-8">
          <p className="text-cs-ink-2">
            <span className="font-medium text-cs-ink">Idea. </span>
            {idea}
          </p>
          <p className="text-cs-ink-2">
            <span className="font-medium text-cs-ink">Trade-off. </span>
            {tradeoff}
          </p>
        </div>
      </div>
      <div className={bleed ? "mt-6" : "cs-container mt-8"}>{children}</div>
    </article>
  );
}
