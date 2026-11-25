import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string | number;
}

/** 各状态名的徽章样式：柔和底色 + 语义文字色 + 状态点。 */
const statusStyles: Record<string, string> = {
  completed: "bg-surface-success text-success",
  passed: "bg-surface-success text-success",
  failed: "bg-surface-destructive text-destructive",
  error: "bg-surface-destructive text-destructive",
  cancelled: "bg-muted text-muted-foreground",
  skipped: "bg-surface-warning text-warning",
  deprecated: "bg-surface-warning text-warning",
  running: "bg-surface-accent text-accent",
  pending: "bg-muted text-muted-foreground",
  active: "bg-surface-success text-success",
  inactive: "bg-muted text-muted-foreground",
  deleted: "bg-muted text-muted-foreground",
};

const DOT_COLORS: Record<string, string> = {
  completed: "bg-success",
  passed: "bg-success",
  active: "bg-success",
  failed: "bg-destructive",
  error: "bg-destructive",
  skipped: "bg-warning",
  deprecated: "bg-warning",
  running: "bg-accent",
  pending: "bg-muted-foreground/50",
  cancelled: "bg-muted-foreground/50",
  inactive: "bg-muted-foreground/50",
  deleted: "bg-muted-foreground/50",
};

const DEFAULT_STYLE = "bg-muted text-muted-foreground";

const STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  passed: "已通过",
  failed: "已失败",
  cancelled: "已中断",
  running: "运行中",
  pending: "等待中",
  skipped: "已跳过",
  error: "错误",
  active: "已启用",
  inactive: "未启用",
  deleted: "已删除",
  deprecated: "已废弃",
};

/** 数值状态（1 启用 / 2 禁用 / 3 删除 / 4 废弃）到语义名的映射。 */
const NUMERIC_STATUS: Record<number, string> = {
  1: "active",
  2: "inactive",
  3: "deleted",
  4: "deprecated",
};

/** 状态徽章：把字符串或数值状态统一渲染为带配色与状态点的标签。 */
export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = (
    typeof status === "number" ? (NUMERIC_STATUS[status] ?? "") : status
  ).toLowerCase();
  const style = statusStyles[normalized] ?? DEFAULT_STYLE;
  const dot = DOT_COLORS[normalized];
  const label =
    STATUS_LABELS[normalized] ??
    (normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : String(status));

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-1.5 text-[12px] font-medium leading-5",
        style
      )}
    >
      {dot && (
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full",
            dot,
            normalized === "running" && "animate-pulse"
          )}
          aria-hidden="true"
        />
      )}
      {label}
    </span>
  );
}
