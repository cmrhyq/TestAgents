/** 单行输入框。 */
import type { InputHTMLAttributes } from "react";
import { forwardRef } from "react";

import { cn } from "@/lib/utils";

const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-8 w-full rounded-md border border-border bg-card px-2.5 text-[13px] leading-5 text-foreground",
          "shadow-none transition-[border-color,box-shadow] duration-150",
          "placeholder:text-muted-foreground",
          "file:border-0 file:bg-transparent file:text-[13px] file:font-medium file:text-foreground",
          "hover:border-border-strong",
          "focus-visible:border-accent/60 focus-visible:shadow-input focus-visible:outline-none",
          "disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
