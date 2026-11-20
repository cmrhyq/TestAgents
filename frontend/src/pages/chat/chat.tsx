import { useEffect, useRef } from "react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { useChat } from "@/hooks/use-chat.ts";
import {
  UserBubble,
  AssistantBubble,
  StreamingTurn,
} from "@/components/chat/message-bubbles";
import { ChatInput } from "@/components/chat/chat-input";
import { useSpace } from "@/hooks/use-spaces";

/**
 * 对话页：作为空间详情的子路由挂在 `/spaces/:spaceId/chat`。
 *
 * 空间由路径参数决定，`conversation_id` 是 URL 中唯一的会话状态源；
 * 会话的新建、切换、删除与重命名都在左侧边栏的空间模块完成，本页不再重复列表。
 * 刷新、分享链接与浏览器前进后退都按 URL 还原，组件内部不保留当前会话的副本。
 */
export default function ChatPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const conversationId = searchParams.get("conversation_id");

  // 空间名仅用于顶部上下文条展示；空间不存在或被删除后跳回仪表盘
  const { data: space, isError: spaceError } = useSpace(spaceId ?? "");

  const {
    instruction,
    mode,
    setMode,
    skillNames,
    toggleSkill,
    pendingUser,
    answer,
    tools,
    error,
    isStreaming,
    hasOverlay,
    serverMessages,
    messagesLoading,
    handleSubmit,
    handleKeyDown,
    handleInstructionChange,
    showWelcome,
  } = useChat({
    conversationId,
    spaceId: spaceId ?? null,
    onConversationCreated: (id) => {
      const next = new URLSearchParams(searchParams);
      next.set("conversation_id", id);
      setSearchParams(next, { replace: true });
    },
  });

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [serverMessages.length, pendingUser, answer, tools.length]);

  if (!spaceId || spaceError) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border-subtle pb-2.5">
        <span className="flex min-w-0 items-center gap-1.5 text-[13px] leading-5">
          <span className="shrink-0 text-muted-foreground">空间</span>
          <span className="truncate font-medium text-foreground">{space?.name ?? "…"}</span>
        </span>
        <span className="hidden shrink-0 text-[12px] text-muted-foreground sm:block">
          上下文已绑定当前空间
        </span>
      </div>

      <div ref={scrollRef} className="flex flex-1 flex-col overflow-y-auto">
        {showWelcome ? (
          <div className="flex flex-1 items-center justify-center">
            <div className="max-w-md text-center">
              <h1 className="text-[24px] font-semibold leading-8 tracking-[-0.02em] text-foreground">
                你想测试什么？
              </h1>
              <p className="mt-1.5 text-[13px] leading-5 text-muted-foreground">
                选好模式与技能，用自然语言下达测试指令。接口、环境与知识库都来自当前空间。
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 py-5">
            {messagesLoading && conversationId && (
              <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:300ms]" />
                <span>加载会话历史…</span>
              </div>
            )}

            {serverMessages.map((msg) =>
              msg.role === "user" ? (
                <UserBubble key={msg.id} content={msg.content} />
              ) : (
                <AssistantBubble key={msg.id} content={msg.content} />
              )
            )}

            {pendingUser !== null && <UserBubble content={pendingUser} />}

            {hasOverlay && (
              <StreamingTurn
                answer={answer}
                tools={tools}
                error={error}
                isStreaming={isStreaming}
              />
            )}
          </div>
        )}
      </div>

      <div className="shrink-0 pb-1 pt-2">
        <ChatInput
          instruction={instruction}
          onInstructionChange={handleInstructionChange}
          onKeyDown={handleKeyDown}
          mode={mode}
          onModeChange={setMode}
          spaceId={spaceId}
          skillNames={skillNames}
          onToggleSkill={toggleSkill}
          isStreaming={isStreaming}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  );
}
