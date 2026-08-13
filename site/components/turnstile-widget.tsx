"use client";

import { useEffect, useRef, useState } from "react";

// Explicit post-hydration rendering, not the implicit script-tag mode.
// The implicit loader mutates DOM that React owns: whenever the cached
// script executed before hydration finished (fast reloads), React hit a
// hydration mismatch (error #418), client-rendered the subtree, and
// destroyed the half-solved widget. The visible symptoms were a missing
// widget after quick back-to-back reloads and submissions carrying
// stale browser-restored tokens, which siteverify rejects as
// timeout-or-duplicate. Rendering from useEffect means React never sees
// DOM it did not create, so the race is gone by construction.
//
// The component also owns the submit flow for its surrounding form:
// fetch-POST instead of a full-page navigation to the endpoint's plain
// text response, a styled inline confirmation, clearing the fields on
// success, and a widget reset after every attempt. The reset matters
// beyond politeness: tokens are single use, so without it a retry or a
// second message would always fail verification. Without JavaScript
// none of this attaches and the native POST still works, matching the
// accepted hard-block trade-off (no JS means no Turnstile token means
// a 403 anyway).

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: Record<string, unknown>) => string;
      reset: (id: string) => void;
      remove: (id: string) => void;
    };
    __csTurnstileOnload?: () => void;
  }
}

const SCRIPT_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js" +
  "?onload=__csTurnstileOnload&render=explicit";

type Status =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "sent"; email: string }
  | { kind: "error"; text: string };

export function TurnstileWidget({ sitekey }: { sitekey: string }) {
  const box = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | undefined>(undefined);
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const form = el.closest("form");
    let disposed = false;

    function renderWidget() {
      if (disposed || !window.turnstile || !el || el.childElementCount) {
        return;
      }
      // The default response field (hidden input named
      // cf-turnstile-response) is injected into the surrounding form,
      // which is what the server verifies.
      widgetId.current = window.turnstile.render(el, { sitekey });
    }

    if (window.turnstile) {
      renderWidget();
    } else {
      window.__csTurnstileOnload = renderWidget;
      if (!document.querySelector(`script[src="${SCRIPT_SRC}"]`)) {
        const s = document.createElement("script");
        s.src = SCRIPT_SRC;
        s.async = true;
        document.head.appendChild(s);
      }
    }

    const submitButton = () =>
      form?.querySelector<HTMLButtonElement>('button[type="submit"]');

    function freshToken() {
      if (widgetId.current && window.turnstile) {
        window.turnstile.reset(widgetId.current);
      }
    }

    async function onSubmit(e: Event) {
      if (!form) return;
      e.preventDefault();
      // Disabled while in flight: tokens are single use, so a double
      // click would burn the token on a request the user never sees.
      const btn = submitButton();
      if (btn) btn.disabled = true;
      setStatus({ kind: "sending" });
      const data = new FormData(form);
      const email = String(data.get("email") || "");
      const body = new URLSearchParams(
        [...data].map(([k, v]) => [k, String(v)]),
      );
      let next: Status;
      try {
        const resp = await fetch(form.action, { method: "POST", body });
        if (resp.ok) {
          form.reset();
          next = { kind: "sent", email };
        } else if (resp.status === 403) {
          next = {
            kind: "error",
            text: "The bot check did not pass. Please try again.",
          };
        } else if (resp.status === 400) {
          next = {
            kind: "error",
            text: "Name, a valid email, and a message are required.",
          };
        } else {
          next = {
            kind: "error",
            text: "Sending failed. Please try again in a minute.",
          };
        }
      } catch {
        next = {
          kind: "error",
          text: "Network error. Please check your connection and try again.",
        };
      }
      // Verified or rejected, the token is spent either way; mint a
      // fresh one so a retry or a second message works without a
      // reload.
      freshToken();
      if (btn) btn.disabled = false;
      setStatus(next);
    }

    // A page restored from the back-forward cache carries the previous,
    // usually expired or already-spent token; reset mints a fresh one.
    function onPageShow(e: PageTransitionEvent) {
      if (!e.persisted) return;
      freshToken();
      const btn = submitButton();
      if (btn) btn.disabled = false;
    }

    form?.addEventListener("submit", onSubmit);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      disposed = true;
      form?.removeEventListener("submit", onSubmit);
      window.removeEventListener("pageshow", onPageShow);
      if (widgetId.current && window.turnstile) {
        window.turnstile.remove(widgetId.current);
      }
    };
  }, [sitekey]);

  return (
    <>
      {status.kind === "sent" && (
        <div
          role="status"
          className="border-cs-sky/40 bg-cs-sky/10 text-cs-ink rounded-xl border px-4 py-3 text-sm"
        >
          <span className="font-medium">Message sent.</span>{" "}
          {status.email
            ? `We will reply to ${status.email}.`
            : "We will get back to you soon."}
        </div>
      )}
      {status.kind === "error" && (
        <div
          role="alert"
          className="rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {status.text}
        </div>
      )}
      <div ref={box} />
    </>
  );
}
