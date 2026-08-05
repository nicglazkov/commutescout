import type { Metadata } from "next";
import { ArrowUpRight, Bug, ShieldAlert } from "lucide-react";

// Contact page takes its own metadata (Task 9 brief). Title/description
// shape follows the pricing page's metadata export (Task 8); description is
// one sentence, Google style.
export const metadata: Metadata = {
  title: "Contact - CommuteScout",
  description:
    "Send the CommuteScout team a message, report a bug on GitHub, or report a security issue privately.",
  alternates: {
    canonical: "https://commutescout.com/contact",
  },
  openGraph: {
    title: "Contact - CommuteScout",
    description:
      "Send the CommuteScout team a message, report a bug on GitHub, or report a security issue privately.",
    url: "https://commutescout.com/contact",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

// "Other ways to reach us" cards. Icons are generic lucide glyphs (bug
// report, security shield, external-link arrow) chosen for the visual
// engagement pass - no brand marks, no new copy. Link destinations and
// visible text are unchanged from the plain-list version this replaces.
const OTHER_WAYS = [
  {
    icon: Bug,
    href: "https://github.com/nicglazkov/commutescout/issues",
    text: "Found a bug? Open a GitHub issue.",
  },
  {
    icon: ShieldAlert,
    href: "https://github.com/nicglazkov/commutescout/security/advisories/new",
    text: "Security issue? Report it privately.",
  },
];

export default function ContactPage() {
  return (
    <>
      {/* Navy header band, matching the /mcp and homepage developer-band
          treatment (bg-cs-navy text-white). Heading and subtitle text are
          unchanged from the previous plain layout. */}
      <section className="bg-cs-navy text-white">
        <div className="mx-auto max-w-5xl px-6 py-14 md:py-20">
          <h1 className="text-balance text-4xl font-medium tracking-tight lg:text-5xl">
            Contact
          </h1>
          <p className="text-white/70 mt-4 max-w-xl text-balance">
            Send a message and the CommuteScout team will get back to you.
          </p>
        </div>
      </section>

      <section className="py-16 md:py-20">
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid gap-12 md:grid-cols-[3fr_2fr] md:gap-10 lg:gap-16">
            <div>
              {/* Plain form POST to /api/contact (Task 11, form-encoded name,
                  email, message): no JS submission handler. The endpoint returns a
                  plain-text response rather than a redirect, so a no-JS submission
                  lands on a plain "Thanks. Your message is on its way." page; that
                  is the accepted v1 behavior, matching the pricing page's waitlist
                  form. Fields, attributes, the honeypot, and the action are
                  unchanged from the previous layout - only the surrounding grid
                  and vertical rhythm changed. */}
              <form method="post" action="/api/contact" className="space-y-5">
                <div>
                  <label htmlFor="name" className="text-cs-ink text-sm font-medium">
                    Name
                  </label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    required
                    maxLength={80}
                    className="border-cs-line bg-cs-paper text-cs-ink placeholder:text-cs-ink/40 focus:ring-cs-sky mt-1.5 w-full rounded-lg border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2"
                  />
                </div>

                <div>
                  <label htmlFor="email" className="text-cs-ink text-sm font-medium">
                    Email
                  </label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    required
                    placeholder="you@example.com"
                    className="border-cs-line bg-cs-paper text-cs-ink placeholder:text-cs-ink/40 focus:ring-cs-sky mt-1.5 w-full rounded-lg border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2"
                  />
                </div>

                <div>
                  <label htmlFor="message" className="text-cs-ink text-sm font-medium">
                    Message
                  </label>
                  <textarea
                    id="message"
                    name="message"
                    required
                    maxLength={2000}
                    rows={6}
                    className="border-cs-line bg-cs-paper text-cs-ink placeholder:text-cs-ink/40 focus:ring-cs-sky mt-1.5 w-full rounded-lg border px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2"
                  />
                </div>

                {/* Honeypot: hidden from sighted users and assistive tech, skipped
                    in tab order. The endpoint returns success without sending if
                    this is filled, same as the pricing page's waitlist form. */}
                <input
                  type="text"
                  name="website"
                  tabIndex={-1}
                  autoComplete="off"
                  className="hidden"
                  aria-hidden="true"
                />

                <button
                  type="submit"
                  className="bg-cs-sky hover:bg-cs-sky/90 rounded-full px-5 py-2.5 text-sm font-medium text-white transition-colors"
                >
                  Send message
                </button>
              </form>
            </div>

            {/* "Other ways to reach us" card: page-owned markup pairing the
                two links that used to sit below the form as a plain list.
                Link destinations and visible text are byte-for-byte the
                same; only the presentation (card, icon, hover state) is
                new. */}
            <div className="border-cs-line bg-cs-paper h-fit rounded-2xl border p-6 lg:p-8">
              <h2 className="text-cs-ink text-lg font-medium">
                Other ways to reach us
              </h2>
              <div className="mt-5 space-y-3">
                {OTHER_WAYS.map(({ icon: Icon, href, text }) => (
                  <a
                    key={href}
                    href={href}
                    className="group border-cs-line hover:border-cs-sky hover:bg-cs-sky/5 flex items-start gap-3 rounded-xl border p-4 transition-colors"
                  >
                    <Icon className="text-cs-sky mt-0.5 size-5 shrink-0" />
                    <span className="text-cs-ink text-sm font-medium">{text}</span>
                    <ArrowUpRight className="text-cs-ink/30 group-hover:text-cs-sky ml-auto mt-0.5 size-4 shrink-0 transition-colors" />
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
