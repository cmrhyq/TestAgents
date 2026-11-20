import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface ReadoutProps {
  label: string;
  value: ReactNode;
  /** 数值配色，默认主文字色 */
  tone?: "default" | "success" | "warning" | "danger";
  /** 是否在标签前显示状态点 */
  dot?: boolean;
}

const TONE_TEXT: Record<NonNullable<ReadoutProps["tone"]>, string> = {
  default: "text-foreground",
  success: "text-success",
  warning: "text-warning",
  danger: "text-destructive",
};

const TONE_DOT: Record<NonNullable<ReadoutProps["tone"]>, string> = {
  default: "bg-muted-foreground/50",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-destructive",
};

/** 读数单元：标签在上、数值在下，用于详情页顶部指标带。 */
export function Readout({ label, value, tone = "default", dot = false }: ReadoutProps) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3">
      <span className="flex items-center gap-1.5 text-[12px] leading-4 text-muted-foreground">
        {dot && (
          <span className={cn("h-1.5 w-1.5 rounded-full", TONE_DOT[tone])} aria-hidden="true" />
        )}
        {label}
      </span>
      <span
        className={cn(
          "text-[24px] font-semibold leading-8 tracking-[-0.02em] tabular-nums",
          TONE_TEXT[tone]
        )}
      >
        {value}
      </span>
    </div>
  );
}

interface ReadoutBandProps {
  children: ReactNode;
  className?: string;
}

/** 指标带容器：一行多个读数，窄屏换行并保留分隔线。 */
export function ReadoutBand({ children, className }: ReadoutBandProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 overflow-hidden rounded-lg border border-border bg-card",
        "sm:grid-cols-3 lg:grid-cols-6 lg:divide-x lg:divide-border-subtle",
        className
      )}
    >
      {children}
    </div>
  );
}
