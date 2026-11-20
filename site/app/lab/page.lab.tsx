import type { Metadata } from "next";
import Link from "next/link";

// Local-only brainstorm index. Files named page.lab.tsx exist only on the dev
// server (see pageExtensions in next.config.ts); production never builds them.
export const metadata: Metadata = {
  title: "Lab (local only)",
  robots: { index: false, follow: false },
};

const BOARDS = [
  { href: "/lab/home", title: "Home page", body: "Hero visual options to replace the single screenshot, and options for the coverage panel under “Clear answers, state by state.”" },
  { href: "/lab/facts", title: "Doc page headers", body: "Options for the fact strips on Data sources, MCP server, REST API and Plugins, and for the REST API header as a whole." },
  { href: "/lab/diagrams", title: "Data sources diagram", body: "Ten diagrams that could replace “Many feeds, one map.”" },
  { href: "/lab/marketplace", title: "Marketplace", body: "Layouts with more color, filters and ways to browse plugins." },
  { href: "/lab/map-sidebar", title: "Map sidebar", body: "What belongs in the sidebar and what belongs elsewhere, then fifteen sidebar designs." },
];

export default function LabIndex() {
  return (
    <main className="cs-container py-16">
      <p className="text-sm text-cs-muted">Local preview only. Not part of the site.</p>
      <h1 className="cs-display mt-2">Lab</h1>
      <p className="mt-4 max-w-2xl text-cs-muted">
        Options to pick from. Each board numbers its options. Annotate the ones you like in review mode, or tell me the numbers.
      </p>
      <ul className="mt-10 grid gap-4 sm:grid-cols-2">
        {BOARDS.map((b) => (
          <li key={b.href}>
            <Link href={b.href} className="block rounded-xl border border-cs-line p-6 hover:border-cs-accent">
              <span className="text-lg font-semibold">{b.title}</span>
              <span className="mt-2 block text-sm text-cs-muted">{b.body}</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
