import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, FileText, Loader2 } from "lucide-react";

import { useAgentRunDetail, useAgentToolCalls } from "@/hooks/use-agent-runs.ts";
import { Button } from "@/components/ui/button.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { Readout, ReadoutBand } from "@/components/shared/readout.tsx";
import { PageHeader } from "@/components/layout/page-header.tsx";
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

  const isActive = data?.status === "running";
  const calls = callsData?.items ?? [];
  // 报告 = 这轮执行里的 send_request，没有 HTTP 调用就没有报告可看
  const hasHttpCalls = calls.some((call) => call.tool_name === "send_request");

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-7 w-64" />
        <ReadoutBand>
          {Array.from({ length: 6 }).map((_, i) => (
            <Readout key={i} label="—" value={<Skeleton className="h-6 w-10" />} />
          ))}
        </ReadoutBand>
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

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={data.title || `执行 ${String(data.id)}`}
        annotation={`执行记录 ${String(data.id)}`}
        meta={
          <>
            <StatusBadge status={data.status} />
            <Badge variant="secondary">{data.mode}</Badge>
            <Badge variant="secondary">{data.trigger_type}</Badge>
            {isActive && <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />}
          </>
        }
        description={
          <span className="tabular-nums">
            {data.llm_provider || "—"} / {data.llm_model || "—"} · 总耗时{" "}
            {formatDurationMs(data.duration_ms)}
          </span>
        }
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-3.5 w-3.5" />
              返回
            </Button>
            {hasHttpCalls && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/reports/${String(data.id)}`)}
              >
                <FileText className="h-3.5 w-3.5" />
                查看报告
              </Button>
            )}
          </>
        }
      />

      {data.error_message && (
        <div className="rounded-lg bg-surface-destructive px-4 py-3 text-[13px] leading-5 text-destructive">
          {data.error_message}
        </div>
      )}

      <ReadoutBand>
        <Readout label="工具调用" value={String(data.tool_call_count)} />
        <Readout label="成功" value={String(data.ok_count)} tone="success" dot />
        <Readout label="失败" value={String(data.error_count)} tone="danger" dot />
        <div className="flex flex-col justify-center gap-1.5 px-4 py-3">
          <span className="text-[12px] leading-4 text-muted-foreground">成功率</span>
          <PassRateBar passed={data.ok_count} total={data.tool_call_count} />
        </div>
        <Readout label="Tokens" value={formatTokens(data.total_tokens)} />
        <Readout label="成本" value={formatCost(data.cost_usd)} />
      </ReadoutBand>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[14px] font-semibold leading-5 text-foreground">
            工具调用留痕
            <span className="ml-1.5 text-[12px] font-normal text-muted-foreground">
              {calls.length || data.tool_call_count} 条
            </span>
          </h2>
          <div className="flex items-center gap-2">
            {!wantBody && (
              <Button variant="outline" size="sm" onClick={() => setWantBody(true)}>
                加载全部正文
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => refetchCalls()}>
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
