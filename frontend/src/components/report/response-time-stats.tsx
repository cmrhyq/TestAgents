import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import type { TestResultDetail } from "@/lib/types.ts";
import { formatResponseTime } from "@/lib/format";
import { computeResponseStats } from "@/lib/stats";

/** 响应耗时统计卡片（avg/min/max/p95）。 */
export function ResponseTimeStats({ results }: { results: TestResultDetail[] }) {
  const stats = computeResponseStats(results.map((r) => r.response_time));
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
              {s.label}响应
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-display text-2xl font-semibold tabular-nums tracking-tight">
              {formatResponseTime(s.value)}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
