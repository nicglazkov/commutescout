import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// Source: Tailark OSS registry, core-utils (https://oss.tailark.com/r/core-utils.json).
// Standard clsx + tailwind-merge combiner, unchanged from upstream.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
