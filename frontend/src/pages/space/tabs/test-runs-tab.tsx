import { DataTable } from "@/components/shared/data-table.tsx";
import { buildTestRunColumns } from "../columns";
import type { TestRun } from "@/lib/types.ts";

export interface TestRunsTabProps {
  data: TestRun[];
  total: number;
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
  page: number;
  pageSize: number;
  onPageChange(page: number): void;
}

export function TestRunsTab({
  data,
  total,
  loading,
  error = false,
  onRetry,
  page,
  pageSize,
  onPageChange,
}: TestRunsTabProps) {
  return (
    <DataTable
      columns={buildTestRunColumns()}
      data={data}
      loading={loading}
      error={error}
      onRetry={onRetry}
      emptyText="该空间暂无测试运行。"
      pagination={{
        page,
        pageSize,
        total,
        onChange: onPageChange,
      }}
    />
  );
}
