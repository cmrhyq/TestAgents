import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  AgentCleanupResult,
  AgentRunDetail,
  AgentRunListResponse,
  AgentToolCallListResponse,
} from "@/lib/types";

interface UseAgentRunsParams {
  space_id?: string | number;
  status?: string;
  page?: number;
  page_size?: number;
}

/** 执行记录列表（/agent/runs）。 */
export function useAgentRuns(params?: UseAgentRunsParams) {
  return useQuery<AgentRunListResponse>({
    queryKey: queryKeys.agentRuns.list(params),
    queryFn: async () => {
      const { data } = await api.get<AgentRunListResponse>("/agent/runs/", {
        params,
      });
      return data;
    },
  });
}

/**
 * 执行记录详情。
 *
 * 只有 `running` 才轮询——改造后没有 `pending` 态（记录插入即为 running），
 * 终态是单条件的 `status !== "running"`。
 */
export function useAgentRunDetail(id: string | number) {
  return useQuery<AgentRunDetail>({
    queryKey: queryKeys.agentRuns.detail(id),
    queryFn: async () => {
      const { data } = await api.get<AgentRunDetail>(`/agent/runs/${id}`);
      return data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" ? 3000 : false;
    },
  });
}

interface UseAgentToolCallsOptions {
  /** 是否拉取请求/响应正文（单条上限 2MB，默认不拉） */
  includeBody?: boolean;
  pageSize?: number;
  enabled?: boolean;
}

/**
 * 某次执行的工具调用留痕。
 *
 * `includeBody=false` 时后端走 `defer(response_body)`，返回体里连字段都没有；
 * 展开某一行时才用 `includeBody=true` 再拉一次（带缓存，不会每次展开都请求）。
 */
export function useAgentToolCalls(
  runId: string | number,
  { includeBody = false, pageSize = 200, enabled = true }: UseAgentToolCallsOptions = {}
) {
  return useQuery<AgentToolCallListResponse>({
    queryKey: queryKeys.agentRuns.toolCalls(runId, includeBody),
    queryFn: async () => {
      const { data } = await api.get<AgentToolCallListResponse>(`/agent/runs/${runId}/tool-calls`, {
        params: { page: 1, page_size: pageSize, include_body: includeBody },
      });
      return data;
    },
    enabled: !!runId && enabled,
  });
}

/** 清理 N 天前的终态执行记录（手动触发，无调度器）。 */
export async function cleanupAgentRuns(params: {
  days?: number;
  space_id?: string | number;
  dry_run?: boolean;
}): Promise<AgentCleanupResult> {
  const { data } = await api.delete<AgentCleanupResult>("/agent/runs/cleanup", {
    params,
  });
  return data;
}
