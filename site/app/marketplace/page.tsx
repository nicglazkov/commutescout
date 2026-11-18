import type { Metadata } from "next";
import Link from "next/link";
import { Marketplace } from "@/components/marketplace";

export const metadata: Metadata = {
  title: "Plugin marketplace - CommuteScout",
  description:
    "Browse the plugins that add alerts to the CommuteScout map and apps: what each one shows, where it covers, who runs it, and whether it is reviewed. All free.",
  alternates: { canonical: "https://commutescout.com/marketplace" },
  openGraph: {
    title: "Plugin marketplace - CommuteScout",
    description:
      "Browse the plugins that add alerts to the CommuteScout map and apps: what each one shows, where it covers, who runs it, and whether it is reviewed. All free.",
    url: "https://commutescout.com/marketplace",
    images: ["/static/shots/og.png"],
  },
  twitter: { card: "summary_large_image", images: ["/static/shots/og.png"] },
};

// Nothing on this page but the tiles: the protocol, the rules and how to
// write a plugin live on /plugins.
export default function MarketplacePage() {
  return (
    <section className="py-14 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex flex-wrap items-end justify-between gap-6 border-b border-cs-line pb-10">
          <div>
            <p className="eyebrow">Plugins &middot; free</p>
            <h1 className="mt-4">Plugin marketplace</h1>
            <p className="mt-4 max-w-[60ch] text-lg leading-relaxed text-cs-muted">
              Plugins add alerts to the map and the apps. Every one here is free. Approved ones are
              reviewed by CommuteScout; the others are public but not reviewed, and say so.
            </p>
          </div>
          <Link href="/plugins" prefetch={false} className="inline-flex h-10 items-center rounded-[var(--site-radius)] px-4 text-sm font-semibold text-cs-ink ring-1 ring-cs-line transition-colors hover:bg-cs-ink/[0.07]">
            Write a plugin
          </Link>
        </div>
        <Marketplace />
      </div>
    </section>
  );
}
