"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import type { Platform } from "@/components/brand/app-install";

// iPhone and Android are shown as equals. When the page is opened on one
// of them, that one moves first and is marked "Your phone"; on a desktop,
// and in the server-rendered HTML, both stay as written (iPhone, Android).

function detect(): Platform | null {
  const ua = navigator.userAgent;
  if (/android/i.test(ua)) return "android";
  // iPadOS reports a Mac user agent; touch points tell them apart.
  if (/iphone|ipod|ipad/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) return "ios";
  return null;
}

const subscribe = () => () => {};

export function usePlatform(): Platform | null {
  return useSyncExternalStore(subscribe, detect, () => null);
}

export function PlatformPair({
  ios,
  android,
  className = "",
  itemClassName = "",
  badgeClassName = "",
}: {
  ios: ReactNode;
  android: ReactNode;
  className?: string;
  itemClassName?: string;
  badgeClassName?: string;
}) {
  const yours = usePlatform();
  const order: Platform[] = yours === "android" ? ["android", "ios"] : ["ios", "android"];
  return (
    <div className={className}>
      {order.map((p) => (
        <div key={p} data-yours={yours === p ? "" : undefined} className={`relative ${itemClassName}`}>
          {yours === p && (
            <span
              className={`cs-data absolute z-10 rounded-full bg-cs-accent px-2 py-0.5 text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-cs-accent-ink ${badgeClassName}`}
            >
              Your phone
            </span>
          )}
          {p === "ios" ? ios : android}
        </div>
      ))}
    </div>
  );
}
