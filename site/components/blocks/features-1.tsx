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
    <section className="pb-16 pt-6 md:pb-20 md:pt-8">
      <div className="mx-auto max-w-7xl px-6">
        <h2 className="text-cs-ink max-w-4xl text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          How it works
        </h2>

        <div className="max-sm:*:not-last:border-cs-line max-sm:*:not-last:border-b max-sm:*:not-last:pb-3 mt-12 grid gap-3 *:max-w-xs sm:grid-cols-2 md:mt-16 md:gap-y-6 lg:grid-cols-4 lg:gap-6">
          {items.map(({ icon: Icon, lead, body }) => (
            <p key={lead} className="text-cs-ink/60 text-balance">
              <span className="text-cs-ink font-medium">
                <Icon className="inline size-4 -translate-y-0.5" /> {lead}
              </span>{" "}
              {body}
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}
