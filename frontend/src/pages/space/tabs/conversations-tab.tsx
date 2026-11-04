import { Link } from "react-router-dom";
import { MessageSquare, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { EmptyState } from "@/components/shared/empty-state.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { useDeleteConversation, useSpaceConversations } from "@/hooks/use-conversations.ts";
import { MODE_LABELS, type ConversationMode } from "@/lib/types";

/**
 * 会话 tab：空间下开过的全部对话。
 *
 * 跳转需同时带上 `space_id`，否则对话页无法加载会话。
 */
export function ConversationsTab({ spaceId }: { spaceId: string }) {
  const { data, isLoading, isError, refetch } = useSpaceConversations(spaceId);
  const deleteConversation = useDeleteConversation();
  const conversations = data?.items ?? [];

  if (isError) {
    return (
      <QueryErrorState
        message="会话列表加载失败"
        action={
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            重试
          </Button>
        }
      />
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-14 animate-pulse rounded-[3px] bg-muted" />
        ))}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <EmptyState
        title="还没有对话"
        description="在对话页选择本空间后开始第一次测试对话。"
        action={
          <Button asChild size="sm">
            <Link to={`/chat?space_id=${spaceId}`}>开始对话</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">共 {data?.total ?? 0} 个会话</p>
        <Button asChild size="sm">
          <Link to={`/chat?space_id=${spaceId}`}>新建对话</Link>
        </Button>
      </div>

      <ul className="divide-y divide-border rounded-[3px] border border-border">
        {conversations.map((conversation) => {
          const mode = (MODE_LABELS[conversation.mode as ConversationMode] ??
            conversation.mode) as string;

          return (
            <li
              key={conversation.id}
              className="flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-muted/50"
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />

              <Link
                to={`/chat?space_id=${spaceId}&conversation_id=${conversation.id}`}
                className="min-w-0 flex-1 no-underline"
              >
                <span className="block truncate text-sm text-foreground">
                  {conversation.title.trim() || "新对话"}
                </span>
                <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground/70">
                  {(conversation.last_message_at ?? conversation.created_at)
                    .slice(0, 16)
                    .replace("T", " ")}
                </span>
              </Link>

              <Badge variant="outline" className="shrink-0 text-[10px]">
                {mode}
              </Badge>

              {conversation.skill_names.length > 0 && (
                <span className="hidden shrink-0 font-mono text-[10px] text-muted-foreground/70 sm:block">
                  +{conversation.skill_names.length} skill
                </span>
              )}

              <button
                type="button"
                aria-label="删除会话"
                onClick={() => deleteConversation.mutate(conversation.id)}
                className="shrink-0 rounded-sm p-1 text-muted-foreground transition-colors hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
