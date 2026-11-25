/** 标签：`variant` 控制配色，其余外观由 `className` 覆盖。 */
import type { HTMLAttributes } from "react";
import { cva } from "class-variance-authority";
import type { VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border border-transparent px-1.5 text-[12px] font-medium leading-5 transition-colors",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground",
        secondary: "bg-muted text-muted-foreground",
        success: "bg-surface-success text-success",
        warning: "bg-surface-warning text-warning",
        info: "bg-surface-accent text-accent",
        destructive: "bg-surface-destructive text-destructive",
        outline: "border-border bg-transparent text-foreground",
      },
    },
    defaultVariants: {
      variant: "secondary",
    },
  }
);

interface BadgeProps extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
export type { BadgeProps };
