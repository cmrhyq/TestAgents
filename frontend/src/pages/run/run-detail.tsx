import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Loader2, FileText } from "lucide-react";

import { useTestRunDetail } from "@/hooks/use-test-runs.ts";
import { useReports } from "@/hooks/use-reports.ts";
import { Button } from "@/components/ui/button.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { HttpMethodBadge } from "@/components/shared/http-method-badge.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { DataTable } from "@/components/shared/data-table.tsx";
import type { Column } from "@/components/shared/data-table.tsx";
import type { TestCaseBrief, TestResultBrief } from "@/lib/types.ts";
import { formatResponseTime } from "@/lib/format";
import { cn } from "@/lib/utils";

interface CaseRow {
  case_name: string;
  method: string;
  url: string;
  status: string;
  response_time: number;
  assertion_passed: number;
  assertion_total: number;
}

function buildCaseRows(cases: TestCaseBrief[], results: TestResultBrief[]): CaseRow[] {
  const resultMap = new Map<string | number, TestResultBrief>();
  for (const r of results) {
    if (r.test_case_id !== null) {
      resultMap.set(r.test_case_id, r);
    }
  }

  return cases.map((tc) => {
    const result = resultMap.get(tc.id);
    return {
      case_name: tc.case_name,
      method: tc.method,
      url: tc.url,
      status: result?.status ?? tc.status,
      response_time: result?.response_time ?? 0,
      assertion_passed: result?.assertion_passed ?? 0,
      assertion_total: result ? result.assertion_passed + result.assertion_failed : 0,
    };
  });
}

const columns: Column<CaseRow & Record<string, unknown>>[] = [
  { key: "case_name", header: "用例名称" },
  {
    key: "method",
    header: "方法",
    render: (_, row) => <HttpMethodBadge method={row.method as string} />,
  },
  { key: "url", header: "URL", className: "font-mono text-xs" },
  {
    key: "status",
    header: "状态",
    render: (_, row) => <StatusBadge status={row.status as string} />,
  },
  {
    key: "response_time",
    header: "耗时",
    render: (val) => (
      <span className="font-mono text-xs tabular-nums">{formatResponseTime(val as number)}</span>
    ),
  },
  {
    key: "assertion_passed",
    header: "断言",
    render: (_, row) => (
      <span className="font-mono text-xs tabular-nums">
        {row.assertion_passed as number}/{row.assertion_total as number}
      </span>
    ),
  },
];

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const runId = id || "";

  const { data, isLoading, isError, refetch } = useTestRunDetail(runId);
  const { data: reportsData } = useReports({ run_id: runId });

  const isActive = data?.status === "running" || data?.status === "pending";
  const isCompleted = data?.status === "completed" || data?.status === "failed";
  const firstReport = reportsData?.items?.[0];

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
          message="加载运行详情失败"
          action={
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      </div>
    );
  }

  const rows = buildCaseRows(data.test_cases, data.test_results);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex flex-1 items-center gap-3">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            {data.name}
          </h1>
          <StatusBadge status={data.status} />
          <span className="rounded-[2px] border border-border bg-muted px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            {data.trigger_type}
          </span>
          {isActive && <Loader2 className="h-4 w-4 animate-spin text-info" />}
        </div>
        {isCompleted && firstReport && (
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

      {/* 结果读数带：mono 读数 + 色点标注，竖墨线分隔 */}
      <div className="rounded-[4px] border border-border bg-card shadow-xs">
        <div className="flex flex-col divide-y divide-border-subtle sm:flex-row sm:divide-x sm:divide-y-0">
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="text-xs text-muted-foreground">用例总数</span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-foreground">
              {data.total_cases}
            </span>
          </div>
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden="true" />
              已通过
            </span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-success">
              {data.passed_cases}
            </span>
          </div>
          <div className="flex flex-1 flex-col justify-center gap-1 px-6 py-5">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-destructive" aria-hidden="true" />
              已失败
            </span>
            <span className="font-display text-3xl font-semibold tabular-nums tracking-tight text-destructive">
              {data.failed_cases}
            </span>
          </div>
          <div className={cn("flex flex-1 flex-col justify-center gap-2 px-6 py-5")}>
            <span className="text-xs text-muted-foreground">通过率</span>
            <PassRateBar passed={data.passed_cases} total={data.total_cases} />
          </div>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={rows as (CaseRow & Record<string, unknown>)[]}
        loading={isActive}
        emptyText="暂无测试用例"
      />
    </div>
  );
}
