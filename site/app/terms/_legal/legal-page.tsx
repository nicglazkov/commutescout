import type { ReactNode } from "react";

import styles from "./legal.module.css";

// Shared layout for /terms and /privacy: a plain-language summary up top,
// then numbered sections with stable anchors and a table of contents
// (sticky beside the text on wide screens, a collapsible list on phones).
// Server-rendered, no client JS: anchors and <details> work without it.

export type LegalSection = {
  id: string;
  title: string;
  body: ReactNode;
};

export function LegalPage({
  eyebrow,
  title,
  effective,
  updated,
  lede,
  summaryTitle,
  summaryNote,
  summary,
  sections,
  foot,
}: {
  eyebrow: string;
  title: string;
  effective: string;
  updated?: string;
  lede: ReactNode;
  summaryTitle: string;
  summaryNote: string;
  summary: ReactNode[];
  sections: LegalSection[];
  foot?: ReactNode;
}) {
  return (
    <div className={styles.page}>
      <div className={styles.wrap}>
        <header>
          <p className={styles.eyebrow}>{eyebrow}</p>
          <h1 className={styles.title}>{title}</h1>
          <p className={styles.meta}>
            <span>
              Effective <strong>{effective}</strong>
            </span>
            {updated ? <span>{updated}</span> : null}
          </p>
          <p className={styles.lede}>{lede}</p>
        </header>

        <section className={styles.summary} aria-labelledby="summary-title">
          <h2 id="summary-title" className={styles.summaryTitle}>
            {summaryTitle}
          </h2>
          <p className={styles.summaryNote}>{summaryNote}</p>
          <ul className={styles.summaryList}>
            {summary.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>

        <div className={styles.grid}>
          <nav className={styles.toc} aria-label="On this page">
            <details className={styles.tocDetails}>
              <summary>On this page</summary>
              <TocList sections={sections} />
            </details>
            <div className={styles.tocWide}>
              <p className={styles.tocLabel}>On this page</p>
              <TocList sections={sections} />
            </div>
          </nav>

          <div className={styles.sections}>
            {sections.map((s, i) => (
              <section
                key={s.id}
                id={s.id}
                className={styles.section}
                aria-labelledby={`${s.id}-h`}
              >
                <div className={styles.sectionHead}>
                  <span className={styles.sectionNum} aria-hidden="true">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h2 id={`${s.id}-h`} className={styles.sectionTitle}>
                    {s.title}
                    <a
                      href={`#${s.id}`}
                      className={styles.anchor}
                      aria-label={`Link to ${s.title}`}
                    >
                      #
                    </a>
                  </h2>
                </div>
                <div className={styles.prose}>{s.body}</div>
              </section>
            ))}
            {foot ? <div className={styles.foot}>{foot}</div> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function TocList({ sections }: { sections: LegalSection[] }) {
  return (
    <ol className={styles.tocList}>
      {sections.map((s, i) => (
        <li key={s.id}>
          <a href={`#${s.id}`}>
            <span className={styles.tocNum} aria-hidden="true">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span>{s.title}</span>
          </a>
        </li>
      ))}
    </ol>
  );
}

export const legalStyles = styles;
