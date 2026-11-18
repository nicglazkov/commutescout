import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Source: Tailark OSS registry, Dusk kit, dusk-button
// (https://oss.tailark.com/r/dusk-button.json). Adapted: every color class
// now points at the shared --cs-* tokens (src/ca_roads_demo/static/tokens.css)
// instead of the kit's own --primary/--secondary/--destructive/etc. slots.
// The "destructive" variant was dropped; this is a marketing site with no
// delete-style actions.
const buttonVariants = cva(
  "cursor-pointer inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--site-radius)] text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cs-sky disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none active:scale-98 duration-200 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-cs-sky text-cs-on-sky font-bold shadow-[0_0_32px_-8px_var(--cs-sky)] hover:bg-cs-sky/90",
        outline:
          "bg-cs-ink/5 ring-1 ring-cs-line duration-200 hover:bg-cs-ink/10",
        secondary: "bg-cs-ink/[0.07] text-cs-ink ring-1 ring-cs-line hover:bg-cs-ink/[0.12]",
        ghost: "text-cs-muted hover:bg-cs-ink/6 hover:text-cs-ink",
        link: "text-cs-sky underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-9 px-4 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5",
        xs: "h-6 px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 px-3 text-[0.8rem] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-2 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-11 px-5 text-[0.95rem] has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5",
        icon: "size-9",
        "icon-xs": "size-6 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
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
