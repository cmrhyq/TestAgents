import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 Tailwind 类名，后出现的冲突类覆盖先前的。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
