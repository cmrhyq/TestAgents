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

/** 执行记录列表，支持按空间、状态与分页筛选。 */
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
 * 仅 `running` 状态按 3 秒间隔轮询，其余状态视为终态不再刷新。
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
  /** 是否拉取请求与响应正文，单条上限 2MB */
  includeBody?: boolean;
  pageSize?: number;
  enabled?: boolean;
}

/**
 * 某次执行的工具调用留痕。
 *
 * `includeBody=false` 时后端不返回正文字段，展开单行时才以 `includeBody=true` 重新请求，
 * 两种形态使用不同的查询键，各自独立缓存。
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

/** 清理指定天数之前的终态执行记录，需手动触发。 */
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
