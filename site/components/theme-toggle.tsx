"use client";

import { useEffect } from "react";

// Sun/moon switch in the site header. Light (Day Drive) is the
// default for every visitor; dark (Night Drive) only appears when the
// visitor picks it here, and the choice is remembered in localStorage
// under THEME_KEY. The inline script in app/layout.tsx applies a stored
// choice before first paint, so there is no flash on load.
//
// Which icon shows is pure CSS (--tt-sun / --tt-moon in globals.css), so
// the server-rendered button is already right before hydration.
export const THEME_KEY = "nd-theme";

function setThemeColor(theme: string) {
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "dark" ? "#0a0d16" : "#f4f3ef");
}

export function ThemeToggle() {
  // A stored Night Drive choice was applied before paint by the head
  // script; match the phone's browser chrome to it once mounted.
  useEffect(() => {
    if (document.documentElement.dataset.theme === "dark") setThemeColor("dark");
  }, []);

  function toggle() {
    const root = document.documentElement;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    if (next === "dark") root.dataset.theme = "dark";
    else delete root.dataset.theme;
    setThemeColor(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Storage blocked (private mode, site data off): the switch still
      // works for this page view, it just is not remembered.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="theme-toggle flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-cs-muted transition-colors hover:bg-cs-ink/[0.07] hover:text-cs-ink"
      title="Switch light or dark"
    >
      <span className="sr-only">Switch between light and dark</span>
      {/* Moon: shown by day, switches to night. */}
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-[18px] w-[18px]" style={{ display: "var(--tt-moon)" }} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
      </svg>
      {/* Sun: shown by night, switches to day. */}
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-[18px] w-[18px]" style={{ display: "var(--tt-sun)" }} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
      </svg>
    </button>
  );
}
