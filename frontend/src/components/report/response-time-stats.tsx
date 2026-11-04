import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import { formatDurationMs } from "@/lib/format";
import { computeResponseStats } from "@/lib/stats";

interface ResponseTimeStatsProps {
  /** 每次工具调用的耗时（毫秒） */
  durations: number[];
  /** 读数标题的后缀，默认「响应」 */
  label?: string;
}

/** 工具调用耗时统计卡片（avg/min/max/p95，单位毫秒）。 */
export function ResponseTimeStats({ durations, label = "响应" }: ResponseTimeStatsProps) {
  const stats = computeResponseStats(durations);
  if (!stats) return null;

  const items = [
    { label: "平均", value: stats.avg },
    { label: "最小", value: stats.min },
    { label: "最大", value: stats.max },
    { label: "P95", value: stats.p95 },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((s) => (
        <Card key={s.label}>
          <CardHeader className="pb-2">
            <CardTitle className="font-mono text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {s.label}
              {label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-display text-2xl font-semibold tabular-nums tracking-tight">
              {formatDurationMs(s.value)}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
