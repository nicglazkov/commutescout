import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";

// Source: Tailark OSS registry, Dusk kit, dusk-pricing-1
// (https://oss.tailark.com/r/dusk-pricing-1.json).
//
// Adapted from upstream: text-muted-foreground/text-foreground/bg-card
// replaced with --cs-* tokens; bare "border" utilities (transparent by
// default in Tailwind v4) given an explicit border-cs-line color; the
// check icon uses cs-sky as a small accent instead of a neutral gray.
// Tier names, prices, and feature bullets are still Tailark's generic
// SaaS placeholders; the pricing page task owns CommuteScout's real plans.
export default function Pricing() {
  return (
    <section className="py-16 md:py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="max-w-sm space-y-6">
          <h1 className="text-cs-ink/60 text-balance text-4xl font-medium tracking-tight lg:text-5xl">
            <span className="text-cs-ink">Pricing</span> that scales with you
          </h1>
        </div>

        <div className="mt-12 grid gap-1.5 border border-cs-line *:p-6 max-lg:mx-auto max-lg:max-w-sm lg:mt-20 lg:grid-cols-4">
          <div className="flex flex-col gap-8 border-cs-line max-lg:border-b lg:border-r">
            <div>
              <p className="text-lg font-medium">Starter</p>
              <p className="text-cs-ink/60 text-lg font-medium">For solo developers</p>

              <div className="my-8 block text-4xl font-medium tracking-tight">
                $19 <span className="text-cs-ink/60 text-lg">/mo</span>
              </div>

              <Button
                variant="outline"
                className="w-full"
                nativeButton={false}
                render={<Link href="#">Get started</Link>}
              />
            </div>

            <ul className="text-cs-ink/60 list-outside space-y-3">
              {["Basic analytics dashboard", "5GB cloud storage", "Email and chat support"].map(
                (item, index) => (
                  <li key={index} className="flex items-center gap-3">
                    <Check className="text-cs-sky size-3" />
                    {item}
                  </li>
                )
              )}
            </ul>
          </div>

          <div className="bg-cs-paper border-cs-line flex flex-col gap-8 max-lg:border-y lg:border-x">
            <div>
              <p className="text-lg font-medium">Pro</p>
              <p className="text-cs-ink/60 text-lg font-medium">For ambitious founders</p>

              <div className="my-8 block text-4xl font-medium tracking-tight">
                $59 <span className="text-cs-ink/60 text-lg">/mo</span>
              </div>

              <Button
                className="w-full"
                nativeButton={false}
                render={<Link href="#">Get started</Link>}
              />
            </div>

            <ul className="text-cs-ink/60 list-outside space-y-3">
              {[
                "Everything in Starter",
                "20GB cloud storage",
                "Email and chat support",
                "Access to community forum",
                "Single user access",
                "Access to basic templates",
                "Mobile app access",
                "1 custom report per month",
                "Monthly product updates",
                "Standard security features",
              ].map((item, index) => (
                <li key={index} className="flex items-center gap-3">
                  <Check className="text-cs-sky size-3" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="border-cs-line flex flex-col gap-8 max-lg:border-y lg:border-x">
            <div>
              <p className="text-lg font-medium">Startup</p>
              <p className="text-cs-ink/60 text-lg font-medium">For growing businesses</p>

              <div className="my-8 block text-4xl font-medium tracking-tight">
                $99 <span className="text-cs-ink/60 text-lg">/mo</span>
              </div>

              <Button
                className="w-full"
                variant="outline"
                nativeButton={false}
                render={<Link href="#">Get started</Link>}
              />
            </div>

            <ul className="text-cs-ink/60 list-outside space-y-3">
              {[
                "Everything in Pro",
                "50GB cloud storage",
                "Email and chat support",
                "12 custom reports per month",
                "Monthly product updates",
                "Standard security features",
              ].map((item, index) => (
                <li key={index} className="flex items-center gap-3">
                  <Check className="text-cs-sky size-3" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="border-cs-line flex flex-col gap-8 max-lg:border-t lg:border-l">
            <div>
              <p className="text-lg font-medium">Enterprise</p>
              <p className="text-cs-ink/60 text-lg font-medium">For large organizations</p>

              <div className="my-8 block text-4xl font-medium tracking-tight">
                $299 <span className="text-cs-ink/60 text-lg">/mo</span>
              </div>

              <Button
                className="w-full"
                variant="outline"
                nativeButton={false}
                render={<Link href="#">Get started</Link>}
              />
            </div>

            <ul className="text-cs-ink/60 list-outside space-y-3">
              {[
                "Everything in Startup",
                "Unlimited cloud storage",
                "Unlimited user access",
                "Daily product updates",
              ].map((item, index) => (
                <li key={index} className="flex items-center gap-3">
                  <Check className="text-cs-sky size-3" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
