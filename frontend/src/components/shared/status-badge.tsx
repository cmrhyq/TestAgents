import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string | number;
}

/** 印章式状态徽章：描边 + mono 标注，pending 用虚线（草稿批注感）。 */
const statusStyles: Record<string, string> = {
  completed: "border-success/50 bg-success/5 text-success",
  passed: "border-success/50 bg-success/5 text-success",
  failed: "border-destructive/50 bg-destructive/5 text-destructive",
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
  running: "运行中",
  pending: "等待中",
  skipped: "已跳过",
  error: "错误",
  active: "已启用",
  inactive: "未启用",
  deleted: "已删除",
  deprecated: "已废弃",
};

/** 数值状态（DataStatus：1 启用 / 2 禁用 / 3 删除 / 4 废弃）→ 语义名。 */
const NUMERIC_STATUS: Record<number, string> = {
  1: "active",
  2: "inactive",
  3: "deleted",
  4: "deprecated",
};

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
