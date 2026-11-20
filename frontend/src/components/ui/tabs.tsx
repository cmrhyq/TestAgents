/** 标签页：WorkBuddy 风格的分段控件（segmented control）。 */
import type { ComponentPropsWithoutRef } from "react";
import { forwardRef } from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

const TabsList = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(
  ({ className, ...props }, ref) => (
    <TabsPrimitive.List
      ref={ref}
      className={cn(
        "spaces-scroll inline-flex h-9 max-w-full items-center gap-0.5 rounded-lg bg-muted p-0.5 text-muted-foreground",
        className
      )}
      {...props}
    />
  )
);
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = forwardRef<
  HTMLButtonElement,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "inline-flex h-8 shrink-0 items-center justify-center whitespace-nowrap rounded-md px-3 text-[13px] font-medium leading-5",
      "transition-[background-color,color,box-shadow] duration-150",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
      "disabled:pointer-events-none disabled:opacity-50",
      "hover:text-foreground",
      "data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-xs",
      className
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
      className
    )}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
