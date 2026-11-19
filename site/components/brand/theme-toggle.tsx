"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

// Light/dark switch. The resolved theme lives on <html data-theme>, set
// before first paint by the inline script in app/layout.tsx; this reads
// it, flips it, and stores the choice under localStorage["cs-theme"].
function subscribe(onChange: () => void) {
  const obs = new MutationObserver(onChange);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => obs.disconnect();
}
const getTheme = () => document.documentElement.dataset.theme ?? "light";

export function ThemeToggle({ className = "" }: { className?: string }) {
  // On the server (and the first client render) the theme is unknown, so
  // both icons are rendered and CSS picks the right one from data-theme.
  const theme = useSyncExternalStore(subscribe, getTheme, () => "unknown");
  const next = theme === "dark" ? "light" : "dark";

  function toggle() {
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("cs-theme", next);
    } catch {
      // Storage blocked (private mode): the switch still works for this page.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "unknown" ? "Switch color theme" : `Switch to ${next} theme`}
      title={theme === "unknown" ? "Switch color theme" : `Switch to ${next} theme`}
      className={`inline-flex size-9 items-center justify-center rounded-[var(--cs-radius-md)] text-cs-ink-2 transition-colors duration-150 hover:bg-cs-surface-2 hover:text-cs-ink ${className}`}
    >
      <Sun aria-hidden className="hidden size-[18px] dark:block" strokeWidth={1.75} />
      <Moon aria-hidden className="size-[18px] dark:hidden" strokeWidth={1.75} />
    </button>
  );
}
