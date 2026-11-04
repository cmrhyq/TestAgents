import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye } from "lucide-react";

import { useReports } from "@/hooks/use-reports.ts";
import { useSpaces } from "@/hooks/use-spaces.ts";
import { Button } from "@/components/ui/button.tsx";
import { DataTable } from "@/components/shared/data-table.tsx";
import { PageHeader } from "@/components/layout/page-header.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.tsx";
import type { Column } from "@/components/shared/data-table.tsx";
import type { Report } from "@/lib/types.ts";
import { formatDurationMs, formatRelativeTime } from "@/lib/format";

type ReportRow = Report & Record<string, unknown>;

const ALL = "__all__";

const STATUS_OPTIONS = [
  { value: "completed", label: "已完成" },
  { value: "failed", label: "已失败" },
  { value: "running", label: "运行中" },
  { value: "cancelled", label: "已中断" },
];

function rateClass(rate: number): string {
  if (rate >= 80) return "text-success";
  if (rate >= 50) return "text-warning";
  return "text-destructive";
}

const columns: Column<ReportRow>[] = [
  {
    key: "run_id",
    header: "RUN",
    render: (val) => (
      <span className="font-mono text-xs tabular-nums text-muted-foreground">{String(val)}</span>
    ),
  },
  {
    key: "title",
    header: "执行标题",
    // 标题可能很长：截断显示，鼠标移入用 title 给出完整内容
    render: (val) => {
      const title = (val as string) || "—";
      return (
        <span className="block max-w-[24rem] truncate font-medium" title={title}>
          {title}
        </span>
      );
    },
  },
  {
    key: "status",
    header: "状态",
    render: (val) => <StatusBadge status={String(val ?? "")} />,
  },
  {
    key: "request_count",
    header: "请求数",
    render: (val) => <span className="font-mono text-sm tabular-nums">{String(val ?? 0)}</span>,
  },
  {
    key: "success_count",
    header: "2xx / 非2xx",
    render: (_, row) => (
      <span className="font-mono text-xs tabular-nums">
        <span className="text-success">{row.success_count}</span>
        <span className="mx-1 text-muted-foreground">/</span>
        <span className={row.error_count > 0 ? "text-destructive" : "text-muted-foreground"}>
          {row.error_count}
        </span>
      </span>
    ),
  },
  {
    key: "exception_count",
    header: "异常",
    render: (val) => (
      <span
        className={
          (val as number) > 0
            ? "font-mono text-xs tabular-nums text-warning"
            : "font-mono text-xs tabular-nums text-muted-foreground"
        }
      >
        {String(val ?? 0)}
      </span>
    ),
  },
  {
    key: "success_rate",
    header: "成功率",
    render: (val) => {
      const rate = Number(val ?? 0);
      return (
        <span className={`font-mono text-sm font-medium tabular-nums ${rateClass(rate)}`}>
          {rate.toFixed(1)}%
        </span>
      );
    },
  },
  {
    key: "avg_duration_ms",
    header: "平均耗时",
    render: (val) => (
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {formatDurationMs(val as number)}
      </span>
    ),
  },
  {
    key: "last_request_at",
    header: "最后请求",
    render: (val) =>
      val ? (
        <span className="font-mono text-xs text-muted-foreground">
          {formatRelativeTime(val as string)}
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
];

/** 报告列表页：查看与下载已生成的报告。 */
export default function ReportsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [spaceId, setSpaceId] = useState<string>(ALL);
  const [status, setStatus] = useState<string>(ALL);
  const pageSize = 20;

  const { data: spacesData } = useSpaces({ page: 1, page_size: 100 });

  const params = useMemo(
    () => ({
      space_id: spaceId === ALL ? undefined : spaceId,
      status: status === ALL ? undefined : status,
      page,
      page_size: pageSize,
    }),
    [spaceId, status, page]
  );

  const { data, isLoading, isError, refetch } = useReports(params);

  const rows: ReportRow[] = (data?.items ?? []) as ReportRow[];

  const actionsColumn: Column<ReportRow> = {
    key: "_actions",
    header: "操作",
    render: (_, row) => (
      <Button
        variant="outline"
        size="sm"
        onClick={() => navigate(`/reports/${String(row.run_id)}`)}
      >
        <Eye className="h-3.5 w-3.5" />
        查看
      </Button>
    ),
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="测试报告"
        annotation="FIG.03 — REPORTS"
        description="按执行（run）汇总的接口调用记录：一行一次执行，点进去看逐条请求与响应。"
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="w-[200px]">
          <Select
            value={spaceId}
            onValueChange={(value) => {
              setSpaceId(value);
              setPage(1);
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="全部空间" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部空间</SelectItem>
              {(spacesData?.items ?? []).map((space) => (
                <SelectItem key={String(space.id)} value={String(space.id)}>
                  {space.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-[160px]">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部状态</SelectItem>
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <span className="font-mono text-xs text-muted-foreground">
          成功率按 HTTP 2xx 计算；「异常」指未拿到响应（网络错误/参数不合法/被拦截）
        </span>
      </div>

      <DataTable
        columns={[...columns, actionsColumn]}
        data={rows}
        loading={isLoading}
        error={isError}
        onRetry={() => refetch()}
        emptyText="暂无报告：还没有执行发过 HTTP 请求"
        pagination={
          data
            ? {
                page,
                pageSize,
                total: data.total,
                onChange: setPage,
              }
            : undefined
        }
      />
    </div>
  );
}
