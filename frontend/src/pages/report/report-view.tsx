import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Download } from "lucide-react";

import { useReportDetail, downloadReport } from "@/hooks/use-reports.ts";
import { Button } from "@/components/ui/button.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import { TestResultsTable } from "@/components/report/test-results-table.tsx";
import { ResponseTimeStats } from "@/components/report/response-time-stats.tsx";
import { cn } from "@/lib/utils";
import { formatDuration } from "@/lib/format";

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

  const { test_run, test_results } = data;
  const failedResults = test_results.filter((r) => r.status === "failed" || r.status === "error");

  const summaryItems = [
    { label: "总数", value: test_run.total_cases, className: "", dot: null as string | null },
    {
      label: "已通过",
      value: test_run.passed_cases,
      className: "text-success",
      dot: "bg-success",
    },
    {
      label: "已失败",
      value: test_run.failed_cases,
      className: "text-destructive",
      dot: "bg-destructive",
    },
    {
      label: "已跳过",
      value: test_run.skipped_cases,
      className: "",
      dot: "bg-muted-foreground/50",
    },
    { label: "错误", value: test_run.error_cases, className: "text-warning", dot: "bg-warning" },
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
            <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
              {test_run.name}
            </h1>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">
              {test_run.llm_provider} / {test_run.llm_model} &middot; 生成于 {data.generated_at}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => downloadReport(data.id)}>
          <Download className="mr-2 h-4 w-4" />
          下载 HTML
        </Button>
      </div>

      {/* 汇总读数带：去卡片化分组横排 */}
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
            <span className="text-xs text-muted-foreground">通过率</span>
            <PassRateBar passed={test_run.passed_cases} total={test_run.total_cases} />
          </div>
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="text-xs text-muted-foreground">耗时</span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">
              {formatDuration(test_run.total_duration)}
            </span>
          </div>
        </div>
      </div>

      {/* 响应时间统计 */}
      <ResponseTimeStats results={test_results} />

      {/* 失败/错误用例 */}
      {failedResults.length > 0 && (
        <div className="space-y-3">
          <h2 className="font-display text-lg font-semibold text-destructive">
            失败 / 错误用例（{failedResults.length}）
          </h2>
          <TestResultsTable results={failedResults} danger />
        </div>
      )}

      {/* 全部测试结果 */}
      <div className="space-y-3">
        <h2 className="font-display text-lg font-semibold text-foreground">
          全部测试结果（{test_results.length}）
        </h2>
        <TestResultsTable results={test_results} />
      </div>
    </div>
  );
}
