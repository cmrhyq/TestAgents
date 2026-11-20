/** 多行输入框。 */
import type { TextareaHTMLAttributes } from "react";
import { forwardRef } from "react";

import { cn } from "@/lib/utils";

const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[60px] w-full rounded-md border border-border bg-card px-2.5 py-1.5 text-[13px] leading-5 text-foreground transition-[border-color,box-shadow] placeholder:text-muted-foreground hover:border-border-strong focus-visible:border-accent/60 focus-visible:shadow-input focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Textarea.displayName = "Textarea";

export { Textarea };
