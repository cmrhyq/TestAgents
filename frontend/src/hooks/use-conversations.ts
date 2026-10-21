import { useQuery } from "@tanstack/react-query";

import { createCrudHooks } from "@/lib/create-crud-hooks";
import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { Conversation, ConversationListResponse, MessageListResponse } from "@/lib/types";

interface UseConversationsParams {
  space_id?: string | number;
  status?: number;
  page?: number;
  page_size?: number;
}

interface CreateConversationPayload {
  space_id?: string | number | null;
  title?: string;
  mode?: string;
  skill_names?: string[];
  environment_id?: string | number | null;
}

interface UpdateConversationPayload {
  title?: string;
  mode?: string;
  skill_names?: string[];
  environment_id?: string | number | null;
  status?: number;
}

const {
  useList: useConversations,
  useUpdate: useUpdateConversation,
  useDelete: useDeleteConversation,
} = createCrudHooks<
  Conversation,
  ConversationListResponse,
  UseConversationsParams,
  CreateConversationPayload,
  UpdateConversationPayload
>({
  queryKeys: queryKeys.conversations,
  basePath: "/conversations",
  labels: {
    createSuccess: "会话创建成功",
    createError: "会话创建失败",
    updateSuccess: "会话更新成功",
    updateError: "会话更新失败",
    deleteSuccess: "会话删除成功",
    deleteError: "会话删除失败",
  },
  toastOnCreate: false,
});

export function useConversationMessages(id: string | number | null | undefined) {
  return useQuery<MessageListResponse>({
    queryKey: queryKeys.conversations.messages(id),
    queryFn: async () => {
      const { data } = await api.get<MessageListResponse>(`/conversations/${id}/messages`);
      return data;
    },
    enabled: !!id,
  });
}

/**
 * 空间下的会话列表（「空间会话」需求的入口）。
 *
 * 单独一个 hook 而非复用 ``useConversations``：这里要按 ``last_message_at`` 倒序、
 * 且只要前 N 条做侧栏列表，不需要分页 UI。
 */
export function useSpaceConversations(
  spaceId: string | number | null | undefined,
  pageSize = 50
) {
  return useQuery<ConversationListResponse>({
    queryKey: queryKeys.conversations.bySpace(spaceId),
    queryFn: async () => {
      const { data } = await api.get<ConversationListResponse>("/conversations/", {
        params: { space_id: spaceId, status: 1, page: 1, page_size: pageSize },
      });
      return data;
    },
    enabled: Boolean(spaceId),
  });
}

export { useConversations, useUpdateConversation, useDeleteConversation };
