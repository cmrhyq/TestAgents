import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Download } from "lucide-react";

import { useReportDetail, downloadReport } from "@/hooks/use-reports.ts";
import { Button } from "@/components/ui/button.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import { ToolCallsTable } from "@/components/report/tool-calls-table.tsx";
import { ResponseTimeStats } from "@/components/report/response-time-stats.tsx";
import { cn } from "@/lib/utils";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/format";

/** 报告详情页：执行汇总、工具耗时统计与工具调用明细。 */
export default function ReportViewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const reportId = id || "";

  const { data, isLoading, isError, refetch } = useReportDetail(reportId);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-[4px]" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-[4px]" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回
        </Button>
        <QueryErrorState
          message="加载报告详情失败"
          action={
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      </div>
    );
  }

  const { run, tool_calls } = data;
  const failedCalls = tool_calls.filter((c) => c.ok !== 1);
  const durations = tool_calls.map((c) => c.duration_ms);

  const summaryItems = [
    { label: "工具调用", value: run.tool_call_count, className: "", dot: null as string | null },
    { label: "已成功", value: run.ok_count, className: "text-success", dot: "bg-success" },
    {
      label: "已失败",
      value: run.error_count,
      className: "text-destructive",
      dot: "bg-destructive",
    },
    {
      label: "LLM 调用",
      value: run.llm_call_count,
      className: "",
      dot: null as string | null,
    },
    {
      label: "Tokens",
      value: formatTokens(run.total_tokens),
      className: "",
      dot: null as string | null,
    },
    {
      label: "成本",
      value: formatCost(run.cost_usd),
      className: "",
      dot: null as string | null,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="annotation mb-1 text-primary">REPORT_{data.id}</div>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
                {run.title || `执行 ${data.run_id}`}
              </h1>
              <StatusBadge status={run.status} />
            </div>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">
              {run.llm_provider || "—"} / {run.llm_model || "—"} &middot; 模式 {run.mode} &middot;
              生成于 {data.generated_at}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => downloadReport(data.id)}>
          <Download className="mr-2 h-4 w-4" />
          下载 HTML
        </Button>
      </div>

      <div className="rounded-[4px] border border-border bg-card shadow-xs">
        <div className="flex flex-col divide-y divide-border-subtle sm:flex-row sm:divide-x sm:divide-y-0">
          {summaryItems.map((item) => (
            <div key={item.label} className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {item.dot && (
                  <span className={cn("h-1.5 w-1.5 rounded-full", item.dot)} aria-hidden="true" />
                )}
                {item.label}
              </span>
              <span
                className={cn(
                  "font-display text-3xl font-semibold tabular-nums tracking-tight",
                  item.className || "text-foreground"
                )}
              >
                {item.value}
              </span>
            </div>
          ))}
          <div className="flex flex-1 flex-col justify-center gap-2 px-6 py-5">
            <span className="text-xs text-muted-foreground">成功率</span>
            <PassRateBar passed={run.ok_count} total={run.tool_call_count} />
          </div>
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="text-xs text-muted-foreground">耗时</span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">
              {formatDurationMs(run.duration_ms)}
            </span>
          </div>
        </div>
      </div>

      <ResponseTimeStats durations={durations} label="工具耗时" />

      {failedCalls.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-display text-lg font-semibold text-destructive">
            失败调用（{failedCalls.length}）
          </h2>
          <ToolCallsTable calls={failedCalls} bodyLoaded emptyText="没有失败的调用" danger />
        </div>
      )}

      <div className="space-y-3">
        <h2 className="font-display text-lg font-semibold text-foreground">
          全部工具调用（{tool_calls.length}）
        </h2>
        <ToolCallsTable calls={tool_calls} bodyLoaded emptyText="这轮执行没有调用任何工具" />
      </div>
    </div>
  );
}
