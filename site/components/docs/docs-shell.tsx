import Link from "next/link";
import { ArrowLeft, ArrowRight, ChevronDown } from "lucide-react";
import { TocList, type TocItem } from "./toc";
import "./docs.css";

export type { TocItem };

const DOCS_NAV = [
  { href: "/developers", label: "REST API" },
  { href: "/mcp", label: "MCP server" },
  { href: "/plugins", label: "Plugins" },
  { href: "/data-sources", label: "Data sources" },
] as const;

type DocsHref = (typeof DOCS_NAV)[number]["href"];

// The frame shared by the four developer pages: a sub-nav between them, a
// page head, an "On this page" rail (sticky on desktop, a disclosure on a
// phone), the reading column, and previous/next links at the end.
export function DocsShell({
  current,
  title,
  dek,
  actions,
  facts,
  toc,
  children,
}: {
  current: DocsHref;
  title: React.ReactNode;
  dek: React.ReactNode;
  actions?: React.ReactNode;
  facts?: { value: string; label: string }[];
  toc: TocItem[];
  children: React.ReactNode;
}) {
  const i = DOCS_NAV.findIndex((n) => n.href === current);
  const prev = i > 0 ? DOCS_NAV[i - 1] : null;
  const next = i < DOCS_NAV.length - 1 ? DOCS_NAV[i + 1] : null;
  return (
    <div className="dx">
      <nav className="dx-subnav" aria-label="Developer documentation">
        <div className="dx-subnav-inner">
          <span className="dx-subnav-label">Developers</span>
          {DOCS_NAV.map((n) => (
            <Link key={n.href} href={n.href} prefetch={false} aria-current={n.href === current ? "page" : undefined}>
              {n.label}
            </Link>
          ))}
        </div>
      </nav>

      <header className="dx-head">
        <div className="dx-head-inner">
          <h1>{title}</h1>
          <p className="dx-dek">{dek}</p>
          {actions ? <div className="dx-head-actions">{actions}</div> : null}
          {facts?.length ? (
            <ul className="dx-facts" aria-label="At a glance" data-count={facts.length}>
              {facts.map((f) => (
                <li key={f.label}>
                  <b>{f.value}</b>
                  <span>{f.label}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </header>

      <div className="dx-body">
        <aside className="dx-toc dx-toc-desk" aria-label="On this page">
          <p className="dx-toc-title">On this page</p>
          <TocList items={toc} />
        </aside>
        <div className="dx-main">
          <details className="dx-toc dx-toc-mobile">
            <summary>
              On this page
              <ChevronDown size={18} aria-hidden="true" />
            </summary>
            <nav aria-label="On this page">
              <TocList items={toc} spy={false} />
            </nav>
          </details>
          {children}
          <nav className="dx-next" aria-label="More developer documentation">
            {prev ? (
              <Link href={prev.href} prefetch={false}>
                <small>
                  <ArrowLeft size={12} aria-hidden="true" style={{ display: "inline", verticalAlign: "-1px" }} /> Previous
                </small>
                <span>{prev.label}</span>
              </Link>
            ) : (
              <span />
            )}
            {next ? (
              <Link href={next.href} prefetch={false} className="dx-next-r">
                <small>
                  Next <ArrowRight size={12} aria-hidden="true" style={{ display: "inline", verticalAlign: "-1px" }} />
                </small>
                <span>{next.label}</span>
              </Link>
            ) : null}
          </nav>
        </div>
      </div>
    </div>
  );
}

// A documentation section: an anchored heading (the id the rail and other
// pages link to), then content.
export function Section({
  id,
  title,
  children,
  labelledBy,
}: {
  id: string;
  title: React.ReactNode;
  children: React.ReactNode;
  labelledBy?: string;
}) {
  const hid = labelledBy ?? `${id}-h`;
  return (
    <section className="dx-sec" aria-labelledby={hid}>
      <h2 id={id} className="dx-sec-h">
        <a href={`#${id}`} className="dx-anchor">
          <span id={hid}>{title}</span>
        </a>
      </h2>
      {children}
    </section>
  );
}
