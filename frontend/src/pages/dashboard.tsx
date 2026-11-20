import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Activity,
  CheckCircle2,
  Folder,
  Globe,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { useSpaces } from "@/hooks/use-spaces";
import { useAgentRuns } from "@/hooks/use-agent-runs";
import { useEndpoints } from "@/hooks/use-endpoints";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  icon: LucideIcon;
  hint?: string;
}

/** 顶部读数卡：一枚指标 + 一行口径说明。 */
function StatCard({ label, value, unit, icon: Icon, hint }: StatCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] leading-4 text-muted-foreground">{label}</span>
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface-accent text-accent">
          <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-[24px] font-semibold leading-8 tracking-[-0.02em] tabular-nums text-foreground">
          {value}
        </span>
        {unit && <span className="text-[12px] text-muted-foreground">{unit}</span>}
      </div>
      {hint && <p className="mt-0.5 text-[11px] leading-4 text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** 仪表盘：关键读数、最近执行与快捷入口。 */
export default function DashboardPage() {
  const { data: spacesData } = useSpaces({ page: 1, page_size: 1 });
  const { data: agentRunsData } = useAgentRuns({ page: 1, page_size: 8 });
  const { data: endpointsData } = useEndpoints({ page: 1, page_size: 1 });

  const stats = useMemo(() => {
    const runs = agentRunsData?.items ?? [];
    const totalCalls = runs.reduce((sum, r) => sum + r.tool_call_count, 0);
    const totalOk = runs.reduce((sum, r) => sum + r.ok_count, 0);
    // 近期执行的成功率按调用次数加权，避免小样本 run 拉偏大盘
    const recentSuccessRate = totalCalls > 0 ? Math.round((totalOk / totalCalls) * 100) : 0;

    return {
      totalSpaces: spacesData?.total ?? 0,
      totalEndpoints: endpointsData?.total ?? 0,
      totalRuns: agentRunsData?.total ?? 0,
      recentSuccessRate,
    };
  }, [spacesData, agentRunsData, endpointsData]);

  const recentRuns = agentRunsData?.items ?? [];

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="仪表盘"
        description="测试空间、接口与执行结果的整体情况。"
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to="/spaces">
              进入测试空间
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="测试空间" value={stats.totalSpaces} icon={Folder} hint="已建立的隔离工作区" />
        <StatCard label="接口总数" value={stats.totalEndpoints} icon={Globe} hint="所有空间登记的接口" />
        <StatCard label="执行记录" value={stats.totalRuns} icon={Activity} hint="累计 Agent 执行轮次" />
        <StatCard
          label="近期成功率"
          value={stats.recentSuccessRate}
          unit="%"
          icon={CheckCircle2}
          hint="最近 8 次执行按调用次数加权"
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {/* 最近执行 */}
        <section className="rounded-lg border border-border bg-card lg:col-span-2">
          <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2.5">
            <h2 className="text-[14px] font-semibold leading-5 text-foreground">最近执行</h2>
            <Link
              to="/reports"
              className="inline-flex items-center gap-1 text-[12px] text-muted-foreground transition-colors hover:text-foreground"
            >
              全部报告
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {recentRuns.length === 0 ? (
            <p className="px-4 py-10 text-center text-[13px] text-muted-foreground">
              还没有执行记录，进入空间发起一次对话试试。
            </p>
          ) : (
            <ul className="divide-y divide-border-subtle">
              {recentRuns.map((run) => (
                <li key={String(run.id)}>
                  <Link
                    to={`/runs/${String(run.id)}`}
                    className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-hover"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium leading-5 text-foreground">
                        {run.title || `执行 ${String(run.id)}`}
                      </p>
                      <p className="truncate text-[11px] leading-4 text-muted-foreground">
                        {run.llm_model || "—"} · {run.tool_call_count} 次工具调用 ·{" "}
                        {formatRelativeTime(run.created_at)}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "shrink-0 text-[13px] font-medium tabular-nums",
                        run.success_rate >= 80
                          ? "text-success"
                          : run.success_rate >= 50
                            ? "text-warning"
                            : "text-destructive"
                      )}
                    >
                      {run.success_rate.toFixed(0)}%
                    </span>
                    <StatusBadge status={run.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 快捷入口 */}
        <section className="flex flex-col gap-3">
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border-subtle px-4 py-2.5">
              <h2 className="text-[14px] font-semibold leading-5 text-foreground">快捷入口</h2>
            </div>
            <div className="flex flex-col p-1.5">
              {[
                { to: "/spaces", label: "管理测试空间", desc: "环境、接口与知识库", icon: Folder },
                { to: "/reports", label: "查看测试报告", desc: "逐条请求与响应", icon: Activity },
                { to: "/skills", label: "技能管理", desc: "扩展 Agent 能力", icon: Sparkles },
              ].map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="flex items-center gap-2.5 rounded-md px-2.5 py-2 transition-colors hover:bg-hover"
                >
                  <item.icon
                    className="h-4 w-4 shrink-0 text-muted-foreground"
                    strokeWidth={1.75}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium leading-5 text-foreground">
                      {item.label}
                    </span>
                    <span className="block truncate text-[11px] leading-4 text-muted-foreground">
                      {item.desc}
                    </span>
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <h2 className="text-[13px] font-semibold leading-5 text-foreground">统计口径</h2>
            <ul className="mt-1.5 flex flex-col gap-1 text-[12px] leading-5 text-muted-foreground">
              <li>· 成功率按 HTTP 2xx 计算</li>
              <li>· 异常指未拿到响应（网络错误 / 参数不合法 / 被拦截）</li>
              <li>· 报告以一次执行（run）为单位汇总</li>
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}
