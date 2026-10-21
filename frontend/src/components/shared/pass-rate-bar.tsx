import { cn } from "@/lib/utils";

interface PassRateBarProps {
  passed: number;
  total: number;
}

/** 蓝图式通过率：mono 读数 + 墨线刻度条（填充带垂直刻度线）。 */
export function PassRateBar({ passed, total }: PassRateBarProps) {
  if (total === 0) {
    return <span className="font-mono text-sm text-muted-foreground">--</span>;
  }

  const percentage = Math.round((passed / total) * 100);

  const barColor =
    percentage >= 80 ? "bg-success" : percentage >= 50 ? "bg-warning" : "bg-destructive";

  const textColor =
    percentage >= 80 ? "text-success" : percentage >= 50 ? "text-warning" : "text-destructive";

  return (
    <div className="flex items-center gap-2">
      <span className={cn("font-mono text-sm font-medium tabular-nums", textColor)}>
        {percentage}%
      </span>
      <div className="h-[6px] w-24 overflow-hidden rounded-[2px] border border-border bg-muted">
        <div
          className={cn("h-full transition-all duration-300 ease-out-expo", barColor)}
          style={{
            width: `${percentage}%`,
            backgroundImage:
              "repeating-linear-gradient(90deg, transparent 0 3px, rgba(255,255,255,0.55) 3px 4px)",
          }}
        />
      </div>
    </div>
  );
}
