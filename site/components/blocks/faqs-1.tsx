"use client";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import Link from "next/link";

// Source: Tailark OSS registry, Dusk kit, dusk-faqs-1
// (https://oss.tailark.com/r/dusk-faqs-1.json). Keeps "use client": the
// accordion needs it for open/closed state, unlike site-header/site-footer
// which have no interactivity to justify it.
//
// Adapted from upstream: text-foreground/text-muted-foreground/text-primary
// replaced with --cs-* tokens. Upstream's copy was written for an ecommerce
// storefront (shipping, returns); replaced with neutral placeholder
// questions since a page composing this block owns its own real FAQ copy.
export default function FAQs() {
  const faqItems = [
    {
      id: "item-1",
      question: "Question placeholder one?",
      answer: "Placeholder answer text. Replace with real content when this block is composed into a page.",
    },
    {
      id: "item-2",
      question: "Question placeholder two?",
      answer: "Placeholder answer text. Replace with real content when this block is composed into a page.",
    },
    {
      id: "item-3",
      question: "Question placeholder three?",
      answer: "Placeholder answer text. Replace with real content when this block is composed into a page.",
    },
    {
      id: "item-4",
      question: "Question placeholder four?",
      answer: "Placeholder answer text. Replace with real content when this block is composed into a page.",
    },
  ];

  return (
    <section className="py-16 md:py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-12 md:grid-cols-2 md:gap-6">
          <h2 className="text-cs-ink max-w-sm text-balance text-4xl font-medium tracking-tight">
            Frequently asked questions
          </h2>

          <div>
            <Accordion className="w-full">
              {faqItems.map((item) => (
                <AccordionItem key={item.id} value={item.id} className="border-dashed">
                  <AccordionTrigger className="cursor-pointer text-base hover:no-underline">
                    {item.question}
                  </AccordionTrigger>
                  <AccordionContent>
                    <p className="text-cs-ink/60 text-base">{item.answer}</p>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>

            <p className="text-cs-ink/60 mt-6">
              Can&apos;t find what you&apos;re looking for? Contact{" "}
              <Link href="/contact" prefetch={false} className="text-cs-sky font-medium hover:underline">
                the CommuteScout team
              </Link>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
