import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { WorkspaceTreeResponse } from "@/lib/types";

/** 空间工作目录树。这是 Agent 的沙箱，也是用户查看产物的入口。 */
export function useWorkspaceTree(spaceId?: string | number | null, maxDepth?: number) {
  return useQuery<WorkspaceTreeResponse>({
    queryKey: [...queryKeys.workspace.tree(spaceId), maxDepth ?? null],
    queryFn: async () => {
      const { data } = await api.get<WorkspaceTreeResponse>(`/spaces/${spaceId}/tree`, {
        params: maxDepth ? { max_depth: maxDepth } : undefined,
      });
      return data;
    },
    enabled: Boolean(spaceId),
  });
}

/** 读取空间的 AGENTS.md（会被注入 system prompt）。 */
export function useAgentsMd(spaceId?: string | number | null) {
  return useQuery<{ content: string }>({
    queryKey: queryKeys.workspace.agentsMd(spaceId),
    queryFn: async () => {
      const { data } = await api.get<{ content: string }>(`/spaces/${spaceId}/agents-md`);
      return data;
    },
    enabled: Boolean(spaceId),
  });
}

/** 覆盖写入 AGENTS.md，下一轮对话即生效。 */
export function useUpdateAgentsMd(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<{ ok: boolean; length: number }, Error, string>({
    mutationFn: async (content) => {
      const { data } = await api.put<{ ok: boolean; length: number }>(
        `/spaces/${spaceId}/agents-md`,
        { content }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workspace.agentsMd(spaceId) });
      toast.success("空间约定已保存，下一轮对话生效");
    },
    onError: (error) => toast.error(error.message || "保存失败"),
  });
}
