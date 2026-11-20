import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";

import { useReportDetail } from "@/hooks/use-reports.ts";
import { Button } from "@/components/ui/button.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import { ReportRequestTable } from "@/components/report/report-request-table.tsx";
import { Readout, ReadoutBand } from "@/components/shared/readout.tsx";
import { PageHeader } from "@/components/layout/page-header.tsx";
import { formatDurationMs, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function ReportViewPage() {
  const { runId: runIdParam } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const runId = runIdParam || "";

  const { data, isLoading, isError, isFetching, refetch } = useReportDetail(runId);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-7 w-64" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[74px] rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" size="sm" className="self-start" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-3.5 w-3.5" />
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

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={run.title || `执行 ${String(run.id)}`}
        annotation={`执行记录 ${String(run.id)}`}
        meta={<StatusBadge status={run.status} />}
        description={
          <span className="tabular-nums">
            {run.llm_provider || "—"} / {run.llm_model || "—"} · 模式 {run.mode} · 最近请求{" "}
            {stat.last_request_at ? formatRelativeTime(stat.last_request_at) : "—"}
          </span>
        }
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-3.5 w-3.5" />
              返回
            </Button>
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
              刷新
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/runs/${String(run.id)}`)}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              执行记录
            </Button>
          </>
        }
      />

      {/* 汇总读数带：成功口径是 HTTP 2xx */}
      <ReadoutBand>
        <Readout label="请求数" value={String(stat.request_count)} />
        <Readout label="2xx 成功" value={String(stat.success_count)} tone="success" dot />
        <Readout label="失败（非 2xx）" value={String(stat.error_count)} tone="danger" dot />
        <Readout label="异常（无响应）" value={String(stat.exception_count)} tone="warning" dot />
        <div className="flex flex-col justify-center gap-1.5 px-4 py-3">
          <span className="text-[12px] leading-4 text-muted-foreground">成功率（2xx）</span>
          <PassRateBar passed={stat.success_count} total={stat.request_count} />
        </div>
        <Readout label="平均耗时" value={formatDurationMs(stat.avg_duration_ms)} />
      </ReadoutBand>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[14px] font-semibold leading-5 text-foreground">
            接口调用
            <span className="ml-1.5 text-[12px] font-normal text-muted-foreground">
              {requests.length} 条
            </span>
          </h2>
          <span className="text-[12px] text-muted-foreground">
            点击任意一行展开请求 / 响应正文（按需加载）
          </span>
        </div>

        <ReportRequestTable runId={String(run.id)} requests={requests} />
      </div>
    </div>
  );
}
