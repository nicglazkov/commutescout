"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

// A one-click copy field for a URL, made for the dark band (homepage and
// /mcp developer sections): mono value, hairline frame, a Copy button that
// confirms in place and announces the result to screen readers.
export function CopyField({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API can be unavailable (insecure context, permissions
      // denied); the URL is still plainly readable and selectable.
    }
  }

  return (
    <div className="flex items-center gap-2 rounded-[var(--cs-radius-md)] border border-cs-band-line bg-[color-mix(in_srgb,var(--cs-band-ink)_6%,transparent)] py-1.5 pl-4 pr-1.5">
      {label && <span className="sr-only">{label}: </span>}
      <code className="cs-data min-w-0 flex-1 break-all text-sm sm:overflow-x-auto sm:whitespace-nowrap sm:break-normal text-cs-band-ink">{value}</code>
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-[var(--cs-radius-sm)] px-3 text-[0.8125rem] font-medium text-cs-band-ink transition-colors hover:bg-[color-mix(in_srgb,var(--cs-band-ink)_10%,transparent)]"
      >
        {copied ? <Check aria-hidden className="size-3.5" /> : <Copy aria-hidden className="size-3.5" />}
        <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}
