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

/** 列出空间下的知识库文档；`spaceId` 为空时不发起请求。 */
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

/** 上传并索引文档；后端同步切片，响应返回时索引已完成。 */
export function useUploadDocument(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<KnowledgeDocument, Error, File>({
    mutationFn: async (file) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<KnowledgeDocument>(`/spaces/${spaceId}/documents`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        // 大文档切片可能超过默认 30 秒超时
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

/** 删除文档并失效文档列表缓存。 */
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

/** 读取文档的切片列表，用于排障与检索效果评估。 */
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
 * 按关键字检索空间知识库，默认取前 5 条命中。
 *
 * 用 mutation 而非 query：检索由用户显式触发，不随输入变化自动请求。
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
