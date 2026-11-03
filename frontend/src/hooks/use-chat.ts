import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useConversationMessages } from "@/hooks/use-conversations.ts";
import { streamChatEvents, type AgentStreamEvent } from "@/lib/stream.ts";
import { queryKeys } from "@/lib/query-keys";
import type { ConversationMode } from "@/lib/types";

/** 一次工具调用的完整记录，用于渲染可折叠卡片。 */
export interface ToolCallRecord {
  id: string;
  name: string;
  args: Record<string, unknown> | null;
  status: "running" | "ok" | "error";
  /** 工具返回内容，后端已截断到 4k 字符 */
  content: string;
  durationMs: number;
}

/** `useChat` 的入参。 */
export interface UseChatParams {
  conversationId: string | null;
  spaceId: string | null;
  /** 新建会话后的回调，由调用方把新会话 ID 写回 URL。 */
  onConversationCreated(conversationId: string): void;
}

const EMPTY_TOOLS: ToolCallRecord[] = [];

/**
 * 对话页的流式状态：把 SSE 事件累积为本地 overlay，并暴露提交与输入控制。
 *
 * overlay 仅在流式期间存在；请求结束后以服务端消息列表为准，不做本地持久化。
 */
export function useChat({ conversationId, spaceId, onConversationCreated }: UseChatParams) {
  const queryClient = useQueryClient();

  const [instruction, setInstruction] = useState("");
  const [mode, setMode] = useState<ConversationMode>("agent");
  const [skillNames, setSkillNames] = useState<string[]>([]);

  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [tools, setTools] = useState<ToolCallRecord[]>(EMPTY_TOOLS);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const { data: messagesData, isLoading: messagesLoading } =
    useConversationMessages(conversationId);
  const serverMessages = messagesData?.items ?? [];

  // 切换会话时清空进行中的 overlay。用 render 期 setState 而非 effect，
  // 避免 effect 晚一帧执行导致旧会话的 overlay 短暂闪现。
  const [trackedConversationId, setTrackedConversationId] = useState(conversationId);
  if (conversationId !== trackedConversationId) {
    setTrackedConversationId(conversationId);
    reset();
  }

  function reset() {
    setPendingUser(null);
    setAnswer("");
    setTools(EMPTY_TOOLS);
    setError(null);
  }

  function applyEvent(event: AgentStreamEvent) {
    switch (event.type) {
      case "text_delta":
        setAnswer((prev) => prev + event.content);
        return;
      case "tool_call":
        setTools((prev) => [
          ...prev,
          {
            id: event.id,
            name: event.name,
            args: event.args,
            status: "running",
            content: "",
            durationMs: 0,
          },
        ]);
        return;
      case "tool_result":
        setTools((prev) =>
          prev.map((call) =>
            call.id === event.id
              ? {
                  ...call,
                  status: event.ok ? "ok" : "error",
                  content: event.content,
                  durationMs: event.duration_ms,
                }
              : call
          )
        );
        return;
      case "final":
        // final 携带完整回答，直接覆盖 delta 拼接结果，避免丢帧造成错位
        setAnswer(event.answer);
        return;
      case "error":
        setError(event.message);
        return;
      case "start":
        return;
    }
  }

  const handleSubmit = async () => {
    if (!instruction.trim() || isStreaming) return;
    if (!spaceId) {
      toast.error("请先选择一个测试空间");
      return;
    }

    const prompt = instruction.trim();
    setInstruction("");
    setPendingUser(prompt);
    setAnswer("");
    setTools(EMPTY_TOOLS);
    setError(null);
    setIsStreaming(true);

    let newConversationId: string | null = null;

    try {
      await streamChatEvents(
        {
          instruction: prompt,
          conversation_id: conversationId ?? undefined,
          mode,
          space_id: spaceId,
          skill_names: skillNames,
        },
        applyEvent,
        {
          onConversationId: (id) => {
            newConversationId = id;
          },
        }
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "请求失败";
      toast.error(message);
      setError(message);
    } finally {
      setIsStreaming(false);

      if (!conversationId && newConversationId) {
        // 新建会话：刷新会话列表后回写 URL，URL 变化会触发 render 期同步逻辑清空 overlay
        await queryClient.invalidateQueries({ queryKey: queryKeys.conversations.all });
        onConversationCreated(newConversationId);
      } else if (conversationId) {
        // 存量会话：必须等消息列表刷新完再清 overlay，否则会出现历史尚未返回、
        // overlay 已消失的空窗
        await queryClient.invalidateQueries({
          queryKey: queryKeys.conversations.messages(conversationId),
        });
        queryClient.invalidateQueries({ queryKey: queryKeys.conversations.all });
        reset();
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInstructionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInstruction(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const toggleSkill = (name: string) => {
    setSkillNames((prev) =>
      prev.includes(name) ? prev.filter((item) => item !== name) : [...prev, name]
    );
  };

  const hasMessages = serverMessages.length > 0 || pendingUser !== null || isStreaming;
  const showWelcome = !hasMessages && !messagesLoading;
  const hasOverlay = pendingUser !== null || isStreaming;

  return {
    // 输入状态
    instruction,
    setInstruction,
    handleInstructionChange,
    handleKeyDown,
    // 上下文选择
    mode,
    setMode,
    skillNames,
    toggleSkill,
    // 流式结果
    pendingUser,
    answer,
    tools,
    error,
    isStreaming,
    hasOverlay,
    serverMessages,
    messagesLoading,
    // 动作
    handleSubmit,
    hasMessages,
    showWelcome,
  };
}
