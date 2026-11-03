import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string | number;
}

/** 各状态名的徽章配色。 */
const statusStyles: Record<string, string> = {
  completed: "border-success/50 bg-success/5 text-success",
  passed: "border-success/50 bg-success/5 text-success",
  failed: "border-destructive/50 bg-destructive/5 text-destructive",
  cancelled: "border-border bg-muted text-muted-foreground",
  error: "border-destructive/50 bg-destructive/5 text-destructive",
  running: "border-info/50 bg-info/5 text-info animate-pulse",
  pending: "border-dashed border-info/60 bg-transparent text-info",
  skipped: "border-warning/50 bg-warning/5 text-warning",
  active: "border-success/50 bg-success/5 text-success",
  inactive: "border-border bg-muted text-muted-foreground",
  deleted: "border-border bg-muted text-muted-foreground",
  deprecated: "border-warning/50 bg-warning/5 text-warning",
};

const DEFAULT_STYLE = "border-border bg-muted text-muted-foreground";

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

/** 状态徽章：把字符串或数值状态统一渲染为带配色的标签。 */
export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = (
    typeof status === "number" ? (NUMERIC_STATUS[status] ?? "") : status
  ).toLowerCase();
  const style = statusStyles[normalized] ?? DEFAULT_STYLE;
  const label =
    STATUS_LABELS[normalized] ??
    (normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : String(status));

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[2px] border px-1.5 py-0.5 font-mono text-[11px] font-medium",
        style
      )}
    >
      {label}
    </span>
  );
}
