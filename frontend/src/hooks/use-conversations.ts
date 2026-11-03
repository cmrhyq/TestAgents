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

// 创建成功不弹 toast，由调用方决定提示方式
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

/** 某会话的消息列表；`id` 为空时不发起请求。 */
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
 * 空间下的会话列表，按 `last_message_at` 倒序取前 N 条。
 *
 * 供侧栏展示，不支持分页；查询键与 `useConversations` 相互独立。
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

/** 会话的增删改查 hook，由 `createCrudHooks` 按 `/conversations` 生成。 */
export { useConversations, useUpdateConversation, useDeleteConversation };
