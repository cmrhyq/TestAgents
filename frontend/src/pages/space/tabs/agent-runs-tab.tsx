import { DataTable } from "@/components/shared/data-table.tsx";
import { useAgentRuns } from "@/hooks/use-agent-runs.ts";
import { buildAgentRunColumns } from "../columns";

const PAGE_SIZE = 10;

/** `AgentRunsTab` 的属性。 */
export interface AgentRunsTabProps {
  /** 当前空间 id，用于查询本空间的执行记录 */
  spaceId: string | number;
  page: number;
  onPageChange(page: number): void;
}

/** 执行记录 tab：表格展示本空间的执行记录。 */
export function AgentRunsTab({ spaceId, page, onPageChange }: AgentRunsTabProps) {
  // 查询放在 tab 内：切到本 tab（组件挂载）时才拉取执行记录
  const { data, isLoading, isError, refetch } = useAgentRuns({
    space_id: spaceId,
    page,
    page_size: PAGE_SIZE,
  });

  return (
    <DataTable
      columns={buildAgentRunColumns()}
      data={data?.items ?? []}
      loading={isLoading}
      error={isError}
      onRetry={() => refetch()}
      emptyText="该空间暂无执行记录。"
      pagination={{
        page,
        pageSize: PAGE_SIZE,
        total: data?.total ?? 0,
        onChange: onPageChange,
      }}
    />
  );
}
