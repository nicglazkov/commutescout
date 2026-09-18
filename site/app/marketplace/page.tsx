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
    <section className="py-12 md:py-16">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-cs-ink md:text-4xl">Plugin marketplace</h1>
            <p className="text-cs-ink/70 mt-2 max-w-2xl text-balance">
              Plugins add alerts to the map and the apps. Every one here is free. Approved ones are
              reviewed by CommuteScout; the others are public but not reviewed, and say so.
            </p>
          </div>
          <Link href="/plugins" prefetch={false} className="text-sm text-cs-sky hover:underline">
            Write a plugin
          </Link>
        </div>
        <Marketplace />
      </div>
    </section>
  );
}
