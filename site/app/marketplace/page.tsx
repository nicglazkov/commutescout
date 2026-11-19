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
    <section className="cs-container pb-20 pt-14 md:pb-28 md:pt-20">
      <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
        <div className="lg:col-span-7">
          <h1 className="cs-display cs-rise">Plugin marketplace</h1>
        </div>
        <div className="cs-rise [animation-delay:120ms] lg:col-span-5">
          <p className="text-[1.0625rem] leading-relaxed text-cs-ink-2">
            Plugins add alerts to the map and the apps. All of them are free. Approved plugins are
            reviewed by CommuteScout. The rest are public and marked as not reviewed.
          </p>
          <Link href="/plugins" prefetch={false} className="cs-link mt-4 inline-flex min-h-6 items-center text-sm">
            Write a plugin
          </Link>
        </div>
      </div>
      <Marketplace />
    </section>
  );
}
