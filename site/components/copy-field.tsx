"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

// Small, page-owned client component (not a vendored Tailark block): the
// homepage's developer band needs a one-click copy for the MCP connector
// URL. Kept separate from site-header/site-footer, which stay
// server-rendered with no "use client" since they have nothing interactive.
export function CopyField({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API can be unavailable (insecure context, permissions
      // denied); the URL is still plainly readable in the field itself.
    }
  }

  return (
    <div className="flex items-center gap-2 rounded-lg bg-white/10 px-4 py-3 ring-1 ring-white/15">
      <code className="flex-1 overflow-x-auto text-sm whitespace-nowrap text-white/90">
        {value}
      </code>
      <button
        type="button"
        onClick={handleCopy}
        className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-md bg-white/10 px-2.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-white/20"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
