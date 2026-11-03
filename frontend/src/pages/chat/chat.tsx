import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";

import { useChat } from "@/hooks/use-chat.ts";
import {
  UserBubble,
  AssistantBubble,
  StreamingTurn,
} from "@/components/chat/message-bubbles";
import { ChatInput } from "@/components/chat/chat-input";
import {
  ConversationListPanel,
  NoSpaceSelected,
} from "@/components/chat/conversation-list";
import { SpaceSelector } from "@/components/space/space-selector";

/**
 * 对话页：URL 中的 `space_id` 与 `conversation_id` 是唯一状态源。
 *
 * 刷新、分享链接与浏览器前进后退都按 URL 还原，组件内部不保留当前会话的副本。
 */
export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const conversationId = searchParams.get("conversation_id");
  const spaceId = searchParams.get("space_id");

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
    spaceId,
    onConversationCreated: (id) => {
      // 保留 space_id：新建会话后仍要停在同一空间里
      const next = new URLSearchParams(searchParams);
      next.set("conversation_id", id);
      setSearchParams(next, { replace: true });
    },
  });

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [serverMessages.length, pendingUser, answer, tools.length]);

  /** 切换空间：同时清空 `conversation_id`，避免跨空间串上下文。 */
  const handleSpaceChange = (nextSpaceId: string | number) => {
    setSearchParams({ space_id: String(nextSpaceId) }, { replace: true });
  };

  const handleSelectConversation = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("conversation_id", id);
    setSearchParams(next, { replace: true });
  };

  const handleNewConversation = () => {
    const next = new URLSearchParams();
    if (spaceId) next.set("space_id", spaceId);
    setSearchParams(next, { replace: true });
  };

  if (!spaceId) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-2">
          <SpaceSelector value={spaceId} onChange={handleSpaceChange} />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <NoSpaceSelected />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <div className="hidden w-[220px] shrink-0 md:block">
        <ConversationListPanel
          spaceId={spaceId}
          activeId={conversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
        />
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-2">
          <SpaceSelector value={spaceId} onChange={handleSpaceChange} />
          <span className="hidden font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70 sm:block">
            Context · Space
          </span>
        </div>

        <div ref={scrollRef} className="flex flex-1 flex-col overflow-y-auto">
          {showWelcome ? (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <h1 className="mt-4 font-display text-3xl font-semibold tracking-tight text-foreground">
                  你想测试什么？
                </h1>
                <p className="mt-2 text-muted-foreground">
                  选好模式与技能，用自然语言下达测试指令
                </p>
              </div>
            </div>
          ) : (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6">
              {messagesLoading && (
                <div className="flex items-center gap-2 font-mono text-sm text-muted-foreground">
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

        <div className="shrink-0 px-4 pb-6">
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
    </div>
  );
}
