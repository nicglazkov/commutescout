import type { Metadata } from "next";
import { ArrowUpRight, Bug, Mail, ShieldAlert } from "lucide-react";

import { TurnstileWidget } from "@/components/turnstile-widget";
import { FormNotice } from "@/components/form-notice";

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

// Turnstile sitekey: a public identifier (same class as the Firebase web
// apiKey), safe to hardcode. The widget is enforcement's visible half;
// the server only rejects tokenless submissions when TURNSTILE_SECRET_KEY
// is set in its environment, so a self-hosted build without Cloudflare
// still has a working form even though this widget errors quietly.
const TURNSTILE_SITEKEY = "0x4AAAAAAEOZmJkCus9gRJcl";

// Other ways to reach us. Same destinations and text as before, plus the
// plain address for anyone who would rather write directly.
const OTHER_WAYS = [
  {
    icon: Mail,
    href: "mailto:hello@commutescout.com",
    text: "Email hello@commutescout.com",
    note: "Pro, partnerships and anything else.",
  },
  {
    icon: Bug,
    href: "https://github.com/nicglazkov/commutescout/issues",
    text: "Found a bug? Open a GitHub issue.",
    note: "Public, so others can see it too.",
  },
  {
    icon: ShieldAlert,
    href: "https://github.com/nicglazkov/commutescout/security/advisories/new",
    text: "Security issue? Report it privately.",
    note: "A private GitHub security advisory.",
  },
];

const field =
  "mt-2 block w-full rounded-[var(--cs-radius-md)] border border-cs-line-strong bg-cs-surface px-3.5 text-[0.9375rem] text-cs-ink placeholder:text-cs-ink-3 transition-colors duration-150 hover:border-cs-ink-3";

export default function ContactPage() {
  return (
    <section className="cs-container pb-20 pt-14 md:pb-28 md:pt-20">
      <div className="grid gap-14 lg:grid-cols-12 lg:gap-10">
        <div className="lg:col-span-5">
          <p className="cs-eyebrow cs-rise">Contact</p>
          <h1 className="cs-display cs-rise mt-5 [animation-delay:60ms]">Write to us.</h1>
          <p className="cs-lede cs-rise mt-6 max-w-[30rem] [animation-delay:120ms]">
            Send a message and the CommuteScout team will get back to you.
          </p>

          <h2 className="cs-eyebrow mt-14">Other ways to reach us</h2>
          <ul className="mt-3 border-t border-cs-line">
            {OTHER_WAYS.map(({ icon: Icon, href, text, note }) => (
              <li key={href} className="border-b border-cs-line">
                <a href={href} className="group flex items-start gap-3.5 py-4">
                  <Icon aria-hidden className="mt-0.5 size-[18px] shrink-0 text-cs-ink-2 transition-colors group-hover:text-cs-accent" strokeWidth={1.75} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[0.9375rem] font-medium text-cs-ink group-hover:text-cs-accent">{text}</span>
                    <span className="mt-0.5 block text-sm text-cs-ink-3">{note}</span>
                  </span>
                  <ArrowUpRight aria-hidden className="mt-0.5 size-4 shrink-0 text-cs-ink-3 transition-transform duration-150 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-cs-accent" />
                </a>
              </li>
            ))}
          </ul>
        </div>

        <div className="lg:col-span-6 lg:col-start-7">
          <div className="rounded-[var(--cs-radius-lg)] border border-cs-line bg-cs-surface p-6 shadow-[var(--cs-shadow-sm)] sm:p-8">
            {/* Plain form POST to /api/contact (name, email, message). A
                browser post comes back here with ?notice=<key>. */}
            <form method="post" action="/api/contact" className="space-y-5">
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="name" className="text-sm font-medium text-cs-ink">
                    Name
                  </label>
                  <input type="text" id="name" name="name" autoComplete="name" required maxLength={80} className={`${field} h-11`} />
                </div>
                <div>
                  <label htmlFor="email" className="text-sm font-medium text-cs-ink">
                    Email
                  </label>
                  <input type="email" id="email" name="email" autoComplete="email" required placeholder="you@example.com" className={`${field} h-11`} />
                </div>
              </div>

              <div>
                <label htmlFor="message" className="text-sm font-medium text-cs-ink">
                  Message
                </label>
                <textarea id="message" name="message" required maxLength={2000} rows={7} className={`${field} resize-y py-3 leading-relaxed`} />
                <p className="mt-1.5 text-xs text-cs-ink-3">Up to 2,000 characters.</p>
              </div>

              {/* Honeypot: hidden, skipped in tab order. The endpoint
                  returns success without sending if this is filled. */}
              <input type="text" name="website" tabIndex={-1} autoComplete="off" className="hidden" aria-hidden="true" />

              {/* Turnstile bot check, rendered after hydration by the
                  client component (see turnstile-widget.tsx). Managed
                  mode is invisible for most visitors, so no height is
                  reserved. The server only enforces it when
                  TURNSTILE_SECRET_KEY is set. */}
              <TurnstileWidget sitekey={TURNSTILE_SITEKEY} />

              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-cs-line pt-5">
                <p className="text-sm text-cs-ink-3">We read every message.</p>
                <button
                  type="submit"
                  className="inline-flex h-11 items-center rounded-[var(--cs-radius-md)] bg-cs-accent px-5 text-[0.9375rem] font-medium text-cs-accent-ink shadow-[var(--cs-shadow-sm)] transition-colors duration-150 hover:bg-cs-accent-hover"
                >
                  Send message
                </button>
              </div>
            </form>
            <FormNotice
              messages={{
                sent: { ok: true, text: "Message sent. We will get back to you soon." },
                invalid: { ok: false, text: "Name, a valid email, and a message are required." },
                verify: { ok: false, text: "The bot check did not pass. Please try again." },
                failed: { ok: false, text: "Sending failed. Please try again in a minute." },
              }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
