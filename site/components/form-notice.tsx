"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

// What a page says after its form was posted by the browser itself. The
// server answers such a post with a redirect back here carrying
// ?notice=<key>, and this shows the matching line. A post the page's own
// script sent never comes this way; the script shows its own status.
export type Notice = { ok: boolean; text: string };

function Line({ messages }: { messages: Record<string, Notice> }) {
  const key = useSearchParams().get("notice");
  const m = key ? messages[key] : undefined;
  if (!m) return null;
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

// useSearchParams needs a Suspense boundary on a statically exported page.
export function FormNotice(props: { messages: Record<string, Notice> }) {
  return (
    <Suspense fallback={null}>
      <Line {...props} />
    </Suspense>
  );
}
