"use client";

import { useEffect, useState } from "react";

// What a page says after its form was posted by the browser itself. The
// server answers such a post with a redirect back here carrying
// ?notice=<key>, and this shows the matching line. A post the page's own
// script sent never comes this way; the script shows its own status.
export type Notice = { ok: boolean; text: string };

export function FormNotice({ messages }: { messages: Record<string, Notice> }) {
  const [key, setKey] = useState<string | null>(null);
  useEffect(() => {
    const k = new URLSearchParams(window.location.search).get("notice");
    if (k && messages[k]) setKey(k);
  }, [messages]);
  if (!key) return null;
  const m = messages[key];
  return (
    <div
      role="status"
      className={
        m.ok
          ? "border-cs-sky/40 bg-cs-sky/10 text-cs-ink mt-4 rounded-xl border px-4 py-3 text-sm"
          : "mt-4 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900"
      }
    >
      {m.text}
    </div>
  );
}
