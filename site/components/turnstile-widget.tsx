"use client";

import { useEffect, useRef } from "react";

// Explicit post-hydration rendering, not the implicit script-tag mode.
// The implicit loader mutates DOM that React owns: whenever the cached
// script executed before hydration finished (fast reloads), React hit a
// hydration mismatch (error #418), client-rendered the subtree, and
// destroyed the half-solved widget. The visible symptoms were a missing
// widget after quick back-to-back reloads and submissions carrying
// stale browser-restored tokens, which siteverify rejects as
// timeout-or-duplicate. Rendering from useEffect means React never sees
// DOM it did not create, so the race is gone by construction.

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

export function TurnstileWidget({ sitekey }: { sitekey: string }) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const form = el.closest("form");
    let widgetId: string | undefined;
    let disposed = false;

    function renderWidget() {
      if (disposed || !window.turnstile || !el || el.childElementCount) {
        return;
      }
      // The default response field (hidden input named
      // cf-turnstile-response) is injected into the surrounding form,
      // which is what the server verifies.
      widgetId = window.turnstile.render(el, { sitekey });
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

    // Tokens are single use: a double click posts the same token twice
    // and the second one always fails verification. Disabling the
    // button after the submit event fires does not cancel the submit
    // already underway; it only swallows the repeat clicks.
    function onSubmit() {
      const btn = submitButton();
      if (btn) btn.disabled = true;
    }

    // A page restored from the back-forward cache carries the previous,
    // usually expired or already-spent token; reset mints a fresh one.
    // The submit button also comes back disabled from the guard above,
    // so it is re-enabled here.
    function onPageShow(e: PageTransitionEvent) {
      if (!e.persisted) return;
      if (widgetId && window.turnstile) window.turnstile.reset(widgetId);
      const btn = submitButton();
      if (btn) btn.disabled = false;
    }

    form?.addEventListener("submit", onSubmit);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      disposed = true;
      form?.removeEventListener("submit", onSubmit);
      window.removeEventListener("pageshow", onPageShow);
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [sitekey]);

  return <div ref={box} />;
}
