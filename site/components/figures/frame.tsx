import type { ReactNode } from "react";
import "./figures.css";

// The card every figure sits in (anatomy convention): Fig n at top left, a short title at top
// right, the drawing, then the hint at bottom left and the live readout at bottom right.
// Legend keys and a true caption go under the card, inside the same <figure>.
export function FigureFrame({
  n,
  title,
  hint,
  readout,
  controls,
  legend,
  caption,
  children,
  className,
  labelledBy,
}: {
  n?: number | string;
  title: string;
  hint?: ReactNode;
  readout?: ReactNode;
  controls?: ReactNode;
  legend?: ReactNode;
  caption?: ReactNode;
  children: ReactNode;
  className?: string;
  labelledBy?: string;
}) {
  return (
    <figure className={`csf${className ? " " + className : ""}`} aria-labelledby={labelledBy}>
      <div className="csf-card">
        <div className="csf-head">
          <span className="csf-num">{n !== undefined ? `Fig. ${n}` : "Figure"}</span>
          <span className="csf-title" id={labelledBy}>
            {title}
          </span>
        </div>
        <div className="csf-stage">{children}</div>
        {controls}
        {(hint || readout) && (
          <div className="csf-foot" style={{ marginTop: controls ? 10 : 0 }}>
            <span className="csf-hint">{hint}</span>
            <span className="csf-readout" data-readout aria-live="polite">
              {readout}
            </span>
          </div>
        )}
      </div>
      {(legend || caption) && (
        <figcaption className="csf-legend">
          {legend}
          {caption && <div className="csf-caption">{caption}</div>}
        </figcaption>
      )}
    </figure>
  );
}
