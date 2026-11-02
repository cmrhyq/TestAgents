import { DataTable } from "@/components/shared/data-table.tsx";
import { buildAgentRunColumns } from "../columns";
import type { AgentRun } from "@/lib/types.ts";

export interface AgentRunsTabProps {
  data: AgentRun[];
  total: number;
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
  page: number;
  pageSize: number;
  onPageChange(page: number): void;
}

export function AgentRunsTab({
  data,
  total,
  loading,
  error = false,
  onRetry,
  page,
  pageSize,
  onPageChange,
}: AgentRunsTabProps) {
  return (
    <DataTable
      columns={buildAgentRunColumns()}
      data={data}
      loading={loading}
      error={error}
      onRetry={onRetry}
      emptyText="该空间暂无执行记录。"
      pagination={{
        page,
        pageSize,
        total,
        onChange: onPageChange,
      }}
    />
  );
}
