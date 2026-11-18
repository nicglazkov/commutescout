import { Eye, MapPinned, MessageCircleQuestion, ShieldAlert } from "lucide-react";

// Source: Tailark OSS registry, Dusk kit, dusk-features-1
// (https://oss.tailark.com/r/dusk-features-1.json). Used for the homepage's
// "How it works" band (Task 7 brief).
//
// Adapted from upstream, beyond colors: dropped the two large illustrated
// "Card" mockups upstream ships above the item list. They carried no real
// content (Tailark's own generic mockup blocks) and the brief gives exact
// copy for only the four-item list below, so this component now composes
// that list alone rather than inventing headline/mockup copy to fill the
// dropped section. The four-item grid is the part of dusk-features-1 that
// maps directly onto the brief's "How it works" spec.
const items = [
  {
    icon: Eye,
    lead: "See it.",
    body: "The live map shows what agencies are reporting right now, refreshed about every 30 seconds.",
  },
  {
    icon: MapPinned,
    lead: "Plan it.",
    body: "Route options with live conditions along the way, exportable to GPX or KML.",
  },
  {
    icon: MessageCircleQuestion,
    lead: "Ask it.",
    body: "Plain-English answers read from the same feeds, with per-source timestamps.",
  },
  {
    icon: ShieldAlert,
    lead: "Watch it.",
    body: "Draw an area and get push or email alerts when something appears inside it.",
  },
];

export default function Features() {
  return (
    <section className="py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-6 md:grid-cols-12">
          <p className="eyebrow md:col-span-3 md:pt-3">How it works</p>
          <h2 className="max-w-3xl md:col-span-9">
            See it. Plan it. Ask it. Watch it.
          </h2>
        </div>

        <ol className="mt-12 grid border-t border-cs-line sm:grid-cols-2 lg:grid-cols-4">
          {items.map(({ icon: Icon, lead, body }, index) => (
            <li
              key={lead}
              className="border-b border-cs-line py-7 sm:pr-6 sm:even:pl-6 lg:border-b-0 lg:border-l lg:pl-6 lg:first:border-l-0 lg:first:pl-0"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-cs-muted">0{index + 1}</span>
                <Icon className="size-5 text-cs-sky" aria-hidden />
              </div>
              <p className="mt-8 font-display text-xl font-bold tracking-tight text-cs-ink">{lead}</p>
              <p className="mt-2 max-w-[34ch] leading-relaxed text-cs-muted">{body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
