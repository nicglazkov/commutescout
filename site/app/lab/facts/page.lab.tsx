import type { Metadata } from "next";
import Link from "next/link";
import "@/components/docs/docs.css";
import "./facts.css";
import { DataSourcesBoard } from "./board-data-sources";
import { McpBoard } from "./board-mcp";
import { RestBoard } from "./board-rest";
import { PluginsBoard } from "./board-plugins";

// Local-only brainstorm board (page.lab.tsx exists only on the dev server).
// Options for the header "fact strip" of the four developer doc pages, and
// for the REST API header as a whole. Every mockup reuses the docs shell's
// header classes, so it renders at the real size; every figure is computed
// from, or cited to, the code (see facts-data.ts and each option's
// "Figures" line).
export const metadata: Metadata = {
  title: "Lab: doc page headers (local only)",
  robots: { index: false, follow: false },
};

const PAGES = [
  {
    id: "data-sources",
    href: "/data-sources",
    name: "Data sources",
    note: "#1 “Change what’s here… give me a shitload of options.”",
    pick: "DS1 Layer ledger",
    why: "It answers the visitor’s real question (what do I get, and where) with seven true counts, and it is honest that depth is uneven. Pair it with DS9’s dated status line if you want freshness up top too.",
    Board: DataSourcesBoard,
  },
  {
    id: "mcp",
    href: "/mcp",
    name: "MCP server",
    note: "#1 “A bunch of different options for what to put in this table.”",
    pick: "M1 Install command, by client",
    why: "People land here to connect. The real add command for their client, one click to copy, does more than any count. Keep M2’s roster as one line under it if there is room.",
    Board: McpBoard,
  },
  {
    id: "developers",
    href: "/developers",
    name: "REST API",
    note: "#1 “Brainstorm all the different things we can put here, maybe instead of this table.” (Also helps #2, Quickstart.)",
    pick: "R1 A real request and its answer",
    why: "The whole contract (URL, key header, JSON shape, data_as_of) in one look, plus a Get a free key button. R5 is the stronger answer if you want the Quickstart itself to be the header.",
    Board: RestBoard,
  },
  {
    id: "plugins",
    href: "/plugins",
    name: "Plugins",
    note: "#1 “Same thing with the table…” (Also #2, the call to action.)",
    pick: "P1 The protocol on one card",
    why: "Five endpoints, two required: a builder sees the size of the job instantly. If the call to action question wins out, P7 makes the path (run, check, get listed) the header instead.",
    Board: PluginsBoard,
  },
];

export default function FactsLab() {
  return (
    <main className="fx-board">
      <header className="fx-intro">
        <div className="fx-wrap">
          <p className="fx-crumb">
            <Link href="/lab">Lab</Link> <span aria-hidden="true">/</span> Local preview only, not part of the site
          </p>
          <h1>Doc page headers</h1>
          <p className="fx-lede">
            Options for the fact strip on four developer pages, and for the REST API header as a whole. Each mockup uses the real
            header markup at real size. Every number is computed from or cited to the code; the “Figures” line under each option says
            where it comes from. No real places appear in any example.
          </p>
          <h2 className="fx-recs-h">Recommended picks</h2>
          <ol className="fx-recs">
            {PAGES.map((p) => (
              <li key={p.id}>
                <a href={`#${p.id}`}>
                  <span className="fx-recs-page">{p.name}</span>
                  <b>{p.pick}</b>
                  <span className="fx-recs-why">{p.why}</span>
                </a>
              </li>
            ))}
          </ol>
          <aside className="fx-flag" aria-label="Found while checking figures">
            <b>Found while checking figures.</b> The live /mcp dek says “Give Claude, ChatGPT, Cursor…”, but
            site/lib/mcp-clients.json lists ChatGPT as “Not yet” (it cannot send the key header). The MCP mockups here leave ChatGPT out
            of the dek.
          </aside>
        </div>
      </header>

      <nav className="fx-jump" aria-label="Boards">
        <div className="fx-wrap">
          {PAGES.map((p) => (
            <a key={p.id} href={`#${p.id}`}>
              {p.name}
            </a>
          ))}
        </div>
      </nav>

      {PAGES.map(({ id, href, name, note, Board }) => (
        <section key={id} className="fx-page" aria-labelledby={`${id}-title`}>
          <div className="fx-wrap fx-page-head">
            <h2 id={id}>
              <span id={`${id}-title`}>{name}</span>{" "}
              <Link href={href} className="fx-page-link">
                {href}
              </Link>
            </h2>
            <p>Note {note}</p>
          </div>
          <Board />
        </section>
      ))}
    </main>
  );
}
