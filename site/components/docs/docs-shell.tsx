import Link from "next/link";
import { ArrowLeft, ArrowRight, ChevronDown } from "lucide-react";
import { TocList, type TocItem } from "./toc";
import "./docs.css";

export type { TocItem };

const DOCS_NAV = [
  { href: "/developers", label: "REST API" },
  { href: "/mcp", label: "MCP Server" },
  { href: "/plugins", label: "Plugins" },
  { href: "/data-sources", label: "Data sources" },
] as const;

type DocsHref = (typeof DOCS_NAV)[number]["href"];
type PagerLink = { href: string; label: string; kicker: string };

// The frame shared by the four developer pages: a sub-nav between them, a
// page head, an "On this page" rail (sticky on desktop, a disclosure on a
// phone), the reading column, and previous/next links at the end.
export function DocsShell({
  current,
  title,
  dek,
  actions,
  facts,
  aside,
  headExtra,
  toc,
  lead,
  children,
}: {
  current: DocsHref;
  title: React.ReactNode;
  dek: React.ReactNode;
  actions?: React.ReactNode;
  facts?: { value: string; label: string }[];
  // The right column of a two-column head (text left, the page's one
  // working object right: the install command on /mcp, a live request on
  // /developers, the layer ledger on /data-sources). Stacks under the
  // text below 1024px.
  aside?: React.ReactNode;
  // Extra content in the text column, under the actions.
  headExtra?: React.ReactNode;
  toc: TocItem[];
  // A full-width band between the head and the body, for the one thing a
  // page must show above the fold (the REST API quickstart).
  lead?: React.ReactNode;
  children: React.ReactNode;
}) {
  // Previous and next follow the sub-nav order. The two ends are never
  // left half-empty: the first page looks back to the live map (the same
  // data, before any code), and the last page leads back to the start.
  const i = DOCS_NAV.findIndex((n) => n.href === current);
  const prev: PagerLink =
    i > 0
      ? { ...DOCS_NAV[i - 1], kicker: "Previous" }
      : { href: "/map", label: "Live map", kicker: "See the data first" };
  const next: PagerLink =
    i < DOCS_NAV.length - 1
      ? { ...DOCS_NAV[i + 1], kicker: "Next" }
      : { ...DOCS_NAV[0], kicker: "Back to the start" };
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
        <div className={"dx-head-inner" + (aside ? " dx-head-split" : "")}>
          <div className="dx-head-main">
            <h1>{title}</h1>
            <p className="dx-dek">{dek}</p>
            {actions ? <div className="dx-head-actions">{actions}</div> : null}
            {headExtra}
          </div>
          {aside ? <div className="dx-head-aside">{aside}</div> : null}
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

      {lead}

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
            <PagerAnchor href={prev.href} className="dx-next-l">
              <ArrowLeft aria-hidden="true" className="dx-next-arrow" />
              <span className="dx-next-text">
                <small>{prev.kicker}</small>
                <span>{prev.label}</span>
              </span>
            </PagerAnchor>
            <PagerAnchor href={next.href} className="dx-next-r">
              <span className="dx-next-text">
                <small>{next.kicker}</small>
                <span>{next.label}</span>
              </span>
              <ArrowRight aria-hidden="true" className="dx-next-arrow" />
            </PagerAnchor>
          </nav>
        </div>
      </div>
    </div>
  );
}

// /map is served by the Python app, not by Next, so it gets a plain link.
function PagerAnchor({ href, className, children }: { href: string; className: string; children: React.ReactNode }) {
  if (href === "/map") {
    return (
      <a href={href} className={className}>
        {children}
      </a>
    );
  }
  return (
    <Link href={href} prefetch={false} className={className}>
      {children}
    </Link>
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
