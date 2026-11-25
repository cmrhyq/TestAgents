import { cn } from "@/lib/utils";

interface PassRateBarProps {
  passed: number;
  total: number;
}

/** 通过率：百分比读数与进度条，总数为 0 时显示占位符。 */
export function PassRateBar({ passed, total }: PassRateBarProps) {
  if (total === 0) {
    return <span className="text-[13px] text-muted-foreground">—</span>;
  }

  const percentage = Math.round((passed / total) * 100);

  const tone = percentage >= 80 ? "bg-success" : percentage >= 50 ? "bg-warning" : "bg-destructive";

  const textColor =
    percentage >= 80 ? "text-success" : percentage >= 50 ? "text-warning" : "text-destructive";

  return (
    <div className="flex items-center gap-2">
      <span className={cn("text-[13px] font-medium leading-5 tabular-nums", textColor)}>
        {percentage}%
      </span>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-accent-strong">
        <div
          className={cn("h-full rounded-full transition-all duration-300 ease-out-expo", tone)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
