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
          ? "mt-4 rounded-[var(--cs-radius-md)] border border-cs-ok/30 bg-cs-ok-soft px-4 py-3 text-sm text-cs-ink"
          : "mt-4 rounded-[var(--cs-radius-md)] border border-cs-closure/30 bg-cs-closure-soft px-4 py-3 text-sm text-cs-ink"
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
