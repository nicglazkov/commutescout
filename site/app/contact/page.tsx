import type { Metadata } from "next";

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

export default function ContactPage() {
  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-xl px-6">
        <h1 className="text-cs-ink text-balance text-4xl font-medium tracking-tight lg:text-5xl">
          Contact
        </h1>

        <p className="text-cs-ink/60 mt-4 text-balance">
          Send a message and the CommuteScout team will get back to you.
        </p>

        {/* Plain form POST to /api/contact (Task 11, form-encoded name,
            email, message): no JS submission handler. The endpoint returns a
            plain-text response rather than a redirect, so a no-JS submission
            lands on a plain "Thanks. Your message is on its way." page; that
            is the accepted v1 behavior, matching the pricing page's waitlist
            form. */}
        <form method="post" action="/api/contact" className="mt-8 space-y-4">
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

        <div className="text-cs-ink/60 mt-10 space-y-2 text-sm">
          <p>
            <a
              href="https://github.com/nicglazkov/commutescout/issues"
              className="text-cs-sky font-medium hover:underline"
            >
              Found a bug? Open a GitHub issue.
            </a>
          </p>
          <p>
            <a
              href="https://github.com/nicglazkov/commutescout/security/advisories/new"
              className="text-cs-sky font-medium hover:underline"
            >
              Security issue? Report it privately.
            </a>
          </p>
        </div>
      </div>
    </section>
  );
}
