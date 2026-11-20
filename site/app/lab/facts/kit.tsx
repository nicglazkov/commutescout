import type { ReactNode } from "react";

// The board's two building blocks.
//
// Head: a copy of the docs shell's page head (components/docs/docs-shell.tsx:
// .dx > .dx-head > .dx-head-inner, title, .dx-dek, .dx-head-actions), so every
// mockup renders at real size with the real type, spacing and tokens. The
// title is a styled <p> instead of an <h1> because the board shows dozens.
// `aside` turns the head into a two-column split (text left, card right).
export function Head({
  title,
  dek,
  actions,
  aside,
  children,
}: {
  title: ReactNode;
  dek: ReactNode;
  actions?: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
}) {
  const text = (
    <>
      <p className="fx-h1">{title}</p>
      <p className="dx-dek">{dek}</p>
      {actions ? <div className="dx-head-actions">{actions}</div> : null}
    </>
  );
  return (
    <div className="dx fx-frame">
      <div className="dx-head">
        <div className="dx-head-inner">
          {aside ? (
            <div className="fx-split">
              <div className="fx-split-text">
                {text}
                {children}
              </div>
              <div className="fx-split-aside">{aside}</div>
            </div>
          ) : (
            <>
              {text}
              {children}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// One numbered option: label row (number, name, idea, trade-off, where the
// figures come from), then the mockup at full width.
export function Opt({
  id,
  n,
  name,
  idea,
  trade,
  src,
  rec,
  children,
}: {
  id: string;
  n: string;
  name: string;
  idea: ReactNode;
  trade: ReactNode;
  src: ReactNode;
  rec?: boolean;
  children: ReactNode;
}) {
  return (
    <article className="fx-opt" id={id} aria-labelledby={`${id}-h`}>
      <div className="fx-opt-meta">
        <h3 id={`${id}-h`} className="fx-opt-h">
          <span className="fx-opt-n">{n}</span>
          {name}
          {rec ? <span className="fx-rec">Recommended</span> : null}
        </h3>
        <div className="fx-opt-notes">
          <p>{idea}</p>
          <p>
            <span className="fx-k">Trade-off</span> {trade}
          </p>
          <p className="fx-src">
            <span className="fx-k">Figures</span> {src}
          </p>
        </div>
      </div>
      <div className="fx-opt-stage">{children}</div>
    </article>
  );
}

// A quiet data row used by several mockups: value then label.
export function Stat({ v, l, sub }: { v: ReactNode; l: ReactNode; sub?: ReactNode }) {
  return (
    <li>
      <b>{v}</b>
      <span>{l}</span>
      {sub ? <small>{sub}</small> : null}
    </li>
  );
}
