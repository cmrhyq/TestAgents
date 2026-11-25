/** 按钮：`variant` 控制视觉变体，`size` 控制尺寸，`asChild` 时把样式交给子元素。 */
import type { ButtonHTMLAttributes } from "react";
import { forwardRef } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import type { VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-[13px] font-medium transition-[background-color,color,border-color,opacity] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // 主行动：单色实心，不用彩色强调
        default:
          "bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/85",
        secondary: "border border-border bg-muted text-foreground hover:bg-hover-strong",
        outline: "border border-border bg-card text-foreground hover:bg-hover",
        ghost: "text-muted-foreground hover:bg-hover hover:text-foreground",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 active:bg-destructive/85",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-8 px-3 [&_svg]:size-4",
        sm: "h-7 gap-1 px-2.5 text-[12px] [&_svg]:size-3.5",
        lg: "h-9 px-4 text-sm [&_svg]:size-4",
        icon: "h-8 w-8 [&_svg]:size-4",
        "icon-sm": "h-7 w-7 [&_svg]:size-3.5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
export type { ButtonProps };
