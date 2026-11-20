import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Source: Tailark OSS registry, Dusk kit, dusk-button
// (https://oss.tailark.com/r/dusk-button.json). Restyled to the Clear Coat
// tokens (app/globals.css, site/DESIGN.md): 10px radius, the one accent
// for primary, hairline outline, quiet ghost. No destructive variant; this
// is a marketing site with no delete-style actions.
const buttonVariants = cva(
  "cursor-pointer inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--cs-radius-md)] text-sm font-medium transition-[background-color,color,box-shadow,transform] duration-150 ease-[var(--cs-ease)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cs-accent disabled:pointer-events-none disabled:opacity-50 active:translate-y-px [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-cs-accent text-cs-accent-ink shadow-[var(--cs-shadow-sm)] hover:bg-cs-accent-hover",
        outline:
          "border border-cs-line-strong bg-cs-surface text-cs-ink shadow-[var(--cs-shadow-sm)] hover:bg-cs-surface-2",
        secondary: "bg-cs-surface-2 text-cs-ink hover:bg-cs-inset",
        ghost: "text-cs-ink-2 hover:bg-cs-surface-2 hover:text-cs-ink",
        link: "text-cs-accent underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-10 px-4 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        xs: "h-6 rounded-[var(--cs-radius-sm)] px-2 text-xs [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 rounded-[var(--cs-radius-sm)] px-3 text-[0.8125rem] [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-11 px-5 text-[0.9375rem] has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4",
        icon: "size-10",
        "icon-xs": "size-6 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
