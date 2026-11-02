import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Folder, Globe, CheckCircle, MessageSquare, Activity } from "lucide-react";

import { useSpaces } from "@/hooks/use-spaces";
import { useAgentRuns } from "@/hooks/use-agent-runs";
import { useEndpoints } from "@/hooks/use-endpoints";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/utils";

/** 图纸角标：四角十字墨线。 */
function CornerMarks() {
  const base = "pointer-events-none absolute h-3 w-3 border-primary";
  return (
    <span aria-hidden="true">
      <span className={cn(base, "left-0 top-0 border-l-2 border-t-2")} />
      <span className={cn(base, "right-0 top-0 border-r-2 border-t-2")} />
      <span className={cn(base, "bottom-0 left-0 border-b-2 border-l-2")} />
      <span className={cn(base, "bottom-0 right-0 border-b-2 border-r-2")} />
    </span>
  );
}

export default function DashboardPage() {
  const { data: spacesData } = useSpaces({ page: 1, page_size: 1 });
  const { data: agentRunsData } = useAgentRuns();
  const { data: endpointsData } = useEndpoints();

  const stats = useMemo(() => {
    const runs = agentRunsData?.items ?? [];
    const totalSpaces = spacesData?.total ?? 0;
    const totalEndpoints = endpointsData?.total ?? 0;
    const totalRuns = agentRunsData?.total ?? 0;

    // 加权成功率：按调用次数汇总再相除，而不是「每个 run 的 success_rate 求平均」。
    // 前者才是真实成功率——一个调了 1 次工具的 run 和一个调了 50 次的 run
    // 在算术平均里权重相同，会把大盘数字带偏。
    const totalCalls = runs.reduce((sum, r) => sum + r.tool_call_count, 0);
    const totalOk = runs.reduce((sum, r) => sum + r.ok_count, 0);
    const avgSuccessRate = totalCalls > 0 ? Math.round((totalOk / totalCalls) * 100) : 0;

    return {
      totalSpaces,
      totalEndpoints,
      totalRuns,
      avgSuccessRate,
    };
  }, [spacesData, agentRunsData, endpointsData]);

  const statItems = [
    { label: "空间总数", value: stats.totalSpaces, unit: "", icon: Folder },
    { label: "接口总数", value: stats.totalEndpoints, unit: "", icon: Globe },
    { label: "执行记录", value: stats.totalRuns, unit: "", icon: Activity },
    { label: "平均成功率", value: stats.avgSuccessRate, unit: "%", icon: CheckCircle },
  ];

  return (
    <div className="flex flex-col gap-8">
      {/* Hero 标题块：图纸网格 + 四角标 + 注解式页头 */}
      <div className="relative overflow-hidden rounded-[4px] border border-border bg-card p-6 shadow-xs lg:p-8">
        <div className="bg-blueprint-grid absolute inset-0" aria-hidden="true" />
        <CornerMarks />
        <div className="relative">
          <PageHeader
            title="仪表盘"
            annotation="FIG.01 — OVERVIEW"
            description="API 测试空间概览。"
            actions={
              <div className="flex items-center gap-2">
                <Button asChild variant="outline">
                  <Link to="/spaces">
                    <Folder className="h-4 w-4" />
                    空间
                  </Link>
                </Button>
                <Button asChild variant="outline">
                  <Link to="/workflows/chat">
                    <MessageSquare className="h-4 w-4" />
                    新建对话
                  </Link>
                </Button>
              </div>
            }
          />
        </div>
      </div>

      {/* 统计读数带：mono 读数 + 竖墨线分隔 */}
      <div className="flex flex-col divide-y divide-border-subtle rounded-[4px] border border-border bg-card shadow-xs sm:flex-row sm:divide-x sm:divide-y-0">
        {statItems.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="flex flex-1 items-center gap-4 px-6 py-5">
              <div className="rounded-[2px] border border-border bg-surface-primary p-2">
                <Icon className="h-4 w-4 text-primary" />
              </div>
              <div>
                <div className="font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">
                  {item.value}
                  {item.unit && (
                    <span className="ml-0.5 font-mono text-sm font-normal text-muted-foreground">
                      {item.unit}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">{item.label}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
