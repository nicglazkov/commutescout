import type { Metadata } from "next";
import Pricing from "@/components/blocks/pricing-1";

// Pricing page takes its own metadata (Task 8 brief). Title/description
// shape follows the homepage's metadata export (Task 7); description is
// one sentence, Google style.
export const metadata: Metadata = {
  title: "Pricing - CommuteScout",
  description:
    "See what's included in CommuteScout's free plan and join the waitlist for Pro: bigger watch areas, event history, and route briefings.",
  alternates: {
    canonical: "https://commutescout.com/pricing",
  },
  openGraph: {
    title: "Pricing - CommuteScout",
    description:
      "See what's included in CommuteScout's free plan and join the waitlist for Pro: bigger watch areas, event history, and route briefings.",
    url: "https://commutescout.com/pricing",
    images: ["/static/shots/og.png"],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/static/shots/og.png"],
  },
};

export default function PricingPage() {
  // The Pro waitlist (form, honeypot, and the #waitlist anchor the
  // homepage hero's "Get Pro updates" CTA scrolls to) lives inside the
  // Pricing block's Pro card since the two-tone redesign, not as a
  // page-owned section here.
  return <Pricing />;
}
