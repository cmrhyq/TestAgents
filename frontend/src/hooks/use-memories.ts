import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  MemoryCreateBody,
  MemoryListResponse,
  MemoryUpdateBody,
  SpaceMemory,
} from "@/lib/types";

/**
 * 列出空间下的跨会话记忆，可按分类过滤。
 *
 * 记忆按空间隔离，不同空间之间互不共享。
 */
export function useMemories(spaceId?: string | number | null, category?: string) {
  return useQuery<MemoryListResponse>({
    queryKey: [...queryKeys.memories.bySpace(spaceId), category ?? "all"],
    queryFn: async () => {
      const { data } = await api.get<MemoryListResponse>(`/spaces/${spaceId}/memories`, {
        params: category ? { category } : undefined,
      });
      return data;
    },
    enabled: Boolean(spaceId),
  });
}

/** 新建记忆并失效记忆缓存。 */
export function useCreateMemory(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<SpaceMemory, Error, MemoryCreateBody>({
    mutationFn: async (payload) => {
      const { data } = await api.post<SpaceMemory>(`/spaces/${spaceId}/memories`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.memories.all });
      toast.success("记忆已保存");
    },
    onError: (error) => toast.error(error.message || "记忆保存失败"),
  });
}

/** 更新记忆并失效记忆缓存。 */
export function useUpdateMemory(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<SpaceMemory, Error, { id: string | number; payload: MemoryUpdateBody }>({
    mutationFn: async ({ id, payload }) => {
      const { data } = await api.put<SpaceMemory>(`/memories/${id}`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.memories.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.memories.bySpace(spaceId) });
      toast.success("记忆已更新");
    },
    onError: (error) => toast.error(error.message || "记忆更新失败"),
  });
}

/** 删除记忆；后端默认软删，并同步重建 MEMORY.md 镜像。 */
export function useDeleteMemory(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string | number>({
    mutationFn: async (id) => {
      await api.delete(`/memories/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.memories.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.memories.bySpace(spaceId) });
      toast.success("记忆已删除");
    },
    onError: (error) => toast.error(error.message || "记忆删除失败"),
  });
}
