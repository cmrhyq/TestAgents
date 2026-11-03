import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Loader2, FileText } from "lucide-react";

import { useAgentRunDetail, useAgentToolCalls } from "@/hooks/use-agent-runs.ts";
import { useReports } from "@/hooks/use-reports.ts";
import { Button } from "@/components/ui/button.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { ToolCallsTable } from "@/components/report/tool-calls-table.tsx";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/format";

/** 执行记录详情页：读数汇总与工具调用留痕。 */
export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const runId = id || "";

  const { data, isLoading, isError, refetch } = useAgentRunDetail(runId);

  // 正文按需加载：单条上限 2MB，一轮执行可能有数十次调用，全量拉取会让详情页体积过大。
  const [wantBody, setWantBody] = useState(false);
  const {
    data: callsData,
    isFetching: callsFetching,
    refetch: refetchCalls,
  } = useAgentToolCalls(runId, { includeBody: wantBody });

  const { data: reportsData } = useReports({ run_id: runId });

  const isActive = data?.status === "running";
  const firstReport = reportsData?.items?.[0];
  const calls = callsData?.items ?? [];

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
          message="加载执行记录详情失败"
          action={
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      </div>
    );
  }

  const readouts = [
    {
      label: "工具调用",
      value: String(data.tool_call_count),
      className: "text-foreground",
      dot: null as string | null,
    },
    { label: "成功", value: String(data.ok_count), className: "text-success", dot: "bg-success" },
    {
      label: "失败",
      value: String(data.error_count),
      className: "text-destructive",
      dot: "bg-destructive",
    },
    {
      label: "LLM 调用",
      value: String(data.llm_call_count),
      className: "text-foreground",
      dot: null,
    },
    {
      label: "Tokens",
      value: formatTokens(data.total_tokens),
      className: "text-foreground",
      dot: null,
    },
    { label: "成本", value: formatCost(data.cost_usd), className: "text-foreground", dot: null },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex flex-1 items-center gap-3">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            {data.title || `执行 ${data.id}`}
          </h1>
          <StatusBadge status={data.status} />
          <span className="rounded-[2px] border border-border bg-muted px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            {data.mode}
          </span>
          <span className="rounded-[2px] border border-border bg-muted px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            {data.trigger_type}
          </span>
          {isActive && <Loader2 className="h-4 w-4 animate-spin text-info" />}
        </div>
        {firstReport && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/reports/${firstReport.id}`)}
          >
            <FileText className="mr-2 h-4 w-4" />
            查看报告
          </Button>
        )}
      </div>

      {data.error_message && (
        <div className="rounded-[4px] border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {data.error_message}
        </div>
      )}

      <div className="rounded-[4px] border border-border bg-card shadow-xs">
        <div className="flex flex-col divide-y divide-border-subtle sm:flex-row sm:divide-x sm:divide-y-0">
          {readouts.map((item) => (
            <div key={item.label} className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {item.dot && (
                  <span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} aria-hidden="true" />
                )}
                {item.label}
              </span>
              <span
                className={`font-display text-3xl font-semibold tabular-nums tracking-tight ${item.className}`}
              >
                {item.value}
              </span>
            </div>
          ))}
          <div className="flex flex-1 flex-col justify-center gap-2 px-6 py-5">
            <span className="text-xs text-muted-foreground">成功率</span>
            <PassRateBar passed={data.ok_count} total={data.tool_call_count} />
          </div>
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="text-xs text-muted-foreground">总耗时</span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">
              {formatDurationMs(data.duration_ms)}
            </span>
          </div>
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="text-xs text-muted-foreground">平均工具耗时</span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">
              {formatDurationMs(data.avg_response_time)}
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold text-foreground">
            工具调用留痕（{calls.length || data.tool_call_count}）
          </h2>
          <div className="flex items-center gap-2">
            {!wantBody && (
              <Button variant="outline" size="sm" onClick={() => setWantBody(true)}>
                加载全部正文
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                refetchCalls();
              }}
            >
              刷新
            </Button>
          </div>
        </div>

        <ToolCallsTable
          calls={calls}
          bodyLoaded={wantBody}
          loadingBody={callsFetching}
          onRequestBody={() => setWantBody(true)}
          emptyText="这轮执行没有调用任何工具"
        />
      </div>
    </div>
  );
}
