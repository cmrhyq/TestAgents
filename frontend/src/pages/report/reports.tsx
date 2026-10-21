import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, Eye } from "lucide-react";

import { useReports, downloadReport } from "@/hooks/use-reports.ts";
import { Button } from "@/components/ui/button.tsx";
import { DataTable } from "@/components/shared/data-table.tsx";
import { PageHeader } from "@/components/layout/page-header.tsx";
import type { Column } from "@/components/shared/data-table.tsx";
import type { Report } from "@/lib/types.ts";
import { formatFileSize } from "@/lib/format";

type ReportRow = Report & Record<string, unknown>;

const columns: Column<ReportRow>[] = [
  {
    key: "test_run_name",
    header: "测试运行",
    render: (val) => <span className="font-medium">{(val as string) || "—"}</span>,
  },
  {
    key: "format",
    header: "格式",
    render: (val) => (
      <span className="inline-flex items-center rounded-[2px] border border-info/50 bg-info/5 px-1.5 py-0.5 font-mono text-[11px] font-medium uppercase text-info">
        {val as string}
      </span>
    ),
  },
  {
    key: "file_size",
    header: "大小",
    render: (val) => (
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {formatFileSize(val as number)}
      </span>
    ),
  },
  {
    key: "generated_at",
    header: "生成时间",
    render: (val) => (
      <span className="font-mono text-xs text-muted-foreground">{val as string}</span>
    ),
  },
];

export default function ReportsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useReports({ page, page_size: pageSize });

  const rows: ReportRow[] = (data?.items ?? []) as ReportRow[];

  const actionsColumn: Column<ReportRow> = {
    key: "_actions",
    header: "操作",
    render: (_, row) => (
      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate(`/reports/${row.id}`)}
        >
          <Eye className="h-3.5 w-3.5" />
          查看
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => downloadReport(row.id)}
        >
          <Download className="h-3.5 w-3.5" />
          下载
        </Button>
      </div>
    ),
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="测试报告"
        annotation="FIG.03 — REPORTS"
        description="查看与下载已生成的测试报告。"
      />

      <DataTable
        columns={[...columns, actionsColumn]}
        data={rows}
        loading={isLoading}
        emptyText="暂无生成的报告"
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
