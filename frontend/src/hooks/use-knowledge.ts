import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type {
  DocumentListResponse,
  KnowledgeChunk,
  KnowledgeDocument,
  SearchResponse,
} from "@/lib/types";

/** 列出空间下的知识库文档。 */
export function useDocuments(spaceId?: string | number | null) {
  return useQuery<DocumentListResponse>({
    queryKey: queryKeys.knowledge.documents(spaceId),
    queryFn: async () => {
      const { data } = await api.get<DocumentListResponse>(`/spaces/${spaceId}/documents`);
      return data;
    },
    enabled: Boolean(spaceId),
  });
}

/** 上传并索引文档。后端同步切片，返回时已完成。 */
export function useUploadDocument(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<KnowledgeDocument, Error, File>({
    mutationFn: async (file) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<KnowledgeDocument>(`/spaces/${spaceId}/documents`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        // 大文档切片可能超过默认 30s
        timeout: 120000,
      });
      return data;
    },
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.documents(spaceId) });
      toast.success(`《${doc.filename}》已索引 ${doc.chunk_count} 个切片`);
    },
    onError: (error) => toast.error(error.message || "文档上传失败"),
  });
}

export function useDeleteDocument(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string | number>({
    mutationFn: async (documentId) => {
      await api.delete(`/documents/${documentId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.documents(spaceId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.all });
      toast.success("文档已删除");
    },
    onError: (error) => toast.error(error.message || "文档删除失败"),
  });
}

/** 以磁盘文件为准重建切片索引。 */
export function useReindexDocument(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<KnowledgeDocument, Error, string | number>({
    mutationFn: async (documentId) => {
      const { data } = await api.post<KnowledgeDocument>(`/documents/${documentId}/reindex`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.knowledge.documents(spaceId) });
      toast.success("重新索引完成");
    },
    onError: (error) => toast.error(error.message || "重新索引失败"),
  });
}

/** 查看文档切片（排障与效果评估）。 */
export function useDocumentChunks(documentId: string | number | null | undefined) {
  return useQuery<KnowledgeChunk[]>({
    queryKey: queryKeys.knowledge.chunks(documentId ?? ""),
    queryFn: async () => {
      const { data } = await api.get<KnowledgeChunk[]>(`/documents/${documentId}/chunks`);
      return data;
    },
    enabled: Boolean(documentId),
  });
}

/**
 * 检索预览：在界面上直接验证「Agent 能查到什么」。
 *
 * 做成 mutation 而不是 query：检索是用户主动触发的动作，
 * 输入框每敲一个字就发一次请求既浪费也没意义。
 */
export function useSearchKnowledge(spaceId?: string | number | null) {
  return useMutation<SearchResponse, Error, { query: string; top_k?: number }>({
    mutationFn: async ({ query, top_k = 5 }) => {
      const { data } = await api.post<SearchResponse>(`/spaces/${spaceId}/documents/search`, {
        query,
        top_k,
      });
      return data;
    },
    onError: (error) => toast.error(error.message || "检索失败"),
  });
}
