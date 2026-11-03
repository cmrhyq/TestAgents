import { MessageSquarePlus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { EmptyState } from "@/components/shared/empty-state.tsx";
import { useDeleteConversation, useSpaceConversations } from "@/hooks/use-conversations.ts";
import { cn } from "@/lib/utils";
import { MODE_LABELS, type ConversationMode } from "@/lib/types";

/** 会话标题的展示值：空标题兜底为「新对话」。 */
function titleOf(title: string): string {
  return title.trim() || "新对话";
}

/** 把后端返回的 ISO 时间串截取到分钟展示。 */
function timeOf(value: string | null): string {
  if (!value) return "";
  return value.slice(5, 16).replace("T", " ");
}

/** `ConversationListPanel` 的属性。 */
export interface ConversationListPanelProps {
  spaceId: string | null;
  activeId: string | null;
  onSelect(conversationId: string): void;
  onNew(): void;
}

/**
 * 会话列表：展示某空间下的全部会话，支持切换与删除。
 *
 * 删除当前正在查看的会话时不做跳转，URL 中的会话失效后页面回落到新建对话状态。
 */
export function ConversationListPanel({
  spaceId,
  activeId,
  onSelect,
  onNew,
}: ConversationListPanelProps) {
  const { data, isLoading } = useSpaceConversations(spaceId);
  const deleteConversation = useDeleteConversation();
  const conversations = data?.items ?? [];

  return (
    <div className="flex h-full min-h-0 flex-col border-r border-border">
      <div className="flex items-center justify-between gap-2 border-b border-border-subtle px-3 py-2">
        <span className="annotation text-muted-foreground">CONVERSATIONS</span>
        <button
          type="button"
          onClick={onNew}
          aria-label="新建对话"
          className="rounded-sm p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <MessageSquarePlus className="h-4 w-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
        {!spaceId ? (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground">请先选择空间</p>
        ) : isLoading ? (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground">加载中…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground">还没有对话</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((conversation) => {
              const active = String(conversation.id) === activeId;
              return (
                <li key={conversation.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(String(conversation.id))}
                    className={cn(
                      "w-full rounded-sm border-l-2 py-1.5 pl-2 pr-7 text-left transition-colors",
                      active
                        ? "border-primary bg-surface-primary"
                        : "border-transparent hover:bg-muted"
                    )}
                  >
                    <span className="block truncate text-xs text-foreground">
                      {titleOf(conversation.title)}
                    </span>
                    <span className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground/70">
                      <span className="uppercase tracking-widest">
                        {MODE_LABELS[conversation.mode as ConversationMode] ?? conversation.mode}
                      </span>
                      <span>·</span>
                      <span>{timeOf(conversation.last_message_at ?? conversation.created_at)}</span>
                    </span>
                  </button>

                  <button
                    type="button"
                    aria-label="删除会话"
                    onClick={() => deleteConversation.mutate(conversation.id)}
                    className="absolute right-1 top-1.5 rounded-sm p-1 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

/** 没有选中空间时的空态。 */
export function NoSpaceSelected() {
  return (
    <EmptyState
      title="先选一个测试空间"
      description="每个空间有独立的工作目录、接口清单、环境、记忆与知识库。"
      action={
        <Button variant="outline" asChild>
          <a href="/spaces">去创建空间</a>
        </Button>
      }
    />
  );
}
