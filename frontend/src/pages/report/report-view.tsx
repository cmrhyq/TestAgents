import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";

import { useReportDetail } from "@/hooks/use-reports.ts";
import { Button } from "@/components/ui/button.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import { ReportRequestTable } from "@/components/report/report-request-table.tsx";
import { formatDurationMs, formatRelativeTime } from "@/lib/format";

export default function ReportViewPage() {
  const { runId: runIdParam } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const runId = runIdParam || "";

  const { data, isLoading, isError, isFetching, refetch } = useReportDetail(runId);

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

  const { run, stat, requests } = data;

  const readouts = [
    {
      label: "请求数",
      value: String(stat.request_count),
      className: "text-foreground",
      dot: null as string | null,
    },
    {
      label: "2xx 成功",
      value: String(stat.success_count),
      className: "text-success",
      dot: "bg-success",
    },
    {
      label: "失败（非 2xx）",
      value: String(stat.error_count),
      className: "text-destructive",
      dot: "bg-destructive",
    },
    {
      label: "异常（无响应）",
      value: String(stat.exception_count),
      className: "text-warning",
      dot: "bg-warning",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-0">
            <div className="annotation mb-1 text-primary">RUN_{String(run.id)}</div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
                {run.title || `执行 ${String(run.id)}`}
              </h1>
              <StatusBadge status={run.status} />
            </div>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">
              {run.llm_provider || "—"} / {run.llm_model || "—"} &middot; 模式 {run.mode} &middot;
              最近请求 {stat.last_request_at ? formatRelativeTime(stat.last_request_at) : "—"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={isFetching ? "mr-2 h-4 w-4 animate-spin" : "mr-2 h-4 w-4"} />
            刷新
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate(`/runs/${String(run.id)}`)}>
            <ExternalLink className="mr-2 h-4 w-4" />
            执行记录
          </Button>
        </div>
      </div>

      {/* 汇总读数带：请求维度统计，成功口径是 HTTP 2xx */}
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
            <span className="text-xs text-muted-foreground">成功率（2xx）</span>
            <PassRateBar passed={stat.success_count} total={stat.request_count} />
          </div>

          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="text-xs text-muted-foreground">平均耗时</span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">
              {formatDurationMs(stat.avg_duration_ms)}
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-lg font-semibold text-foreground">
            接口调用（{requests.length}）
          </h2>
          <span className="font-mono text-xs text-muted-foreground">
            点击任意一行展开请求 / 响应正文（按需加载）
          </span>
        </div>

        <ReportRequestTable runId={String(run.id)} requests={requests} />
      </div>
    </div>
  );
}
