import type { ConversationMode } from "@/lib/types/conversation.ts";

/** 对话流式请求体。 */
export interface ChatStreamRequest {
  instruction: string;
  conversation_id?: string | number | null;
  space_id?: string | number | null;
  mode?: ConversationMode | string;
  /** 选中的 skill 名，后端会把对应 SKILL.md 正文注入 system prompt */
  skill_names?: string[];
  /** 指定测试环境；不传时由 Agent 自行调用 list_environments 选择 */
  environment_id?: string | number | null;
}

/** 流式请求的可选配置。 */
export interface StreamChatOptions {
  signal?: AbortSignal;
  /** 从响应头 X-Conversation-Id 读到会话 ID 时触发，用于新建会话回写 */
  onConversationId?: (conversationId: string) => void;
}

/**
 * Agent 流式事件，`/chat/stream` 的三种模式共用。
 *
 * 类型固定为 `start`、`text_delta`、`tool_call`、`tool_result`、`final`、`error`。
 * `final` 携带完整回答，前端不应依赖拼接 `text_delta` 得到答案：丢帧或重连会让拼接结果错位。
 */
export type AgentStreamEvent =
  | {
      type: "start";
      seq: number;
      conversation_id: string | number | null;
      space_id: string | number | null;
      mode: string;
      skills: string[];
    }
  | { type: "text_delta"; seq: number; content: string }
  | { type: "tool_call"; seq: number; id: string; name: string; args: Record<string, unknown> }
  | {
      type: "tool_result";
      seq: number;
      id: string;
      name: string;
      ok: boolean;
      /** 后端截断到 4k 字符 */
      content: string;
      duration_ms: number;
    }
  | { type: "final"; seq: number; answer: string; usage: Record<string, unknown> }
  | { type: "error"; seq: number; message: string };

/** `AgentStreamEvent` 的旧名别名，保留供既有代码使用。 */
export type StreamRunEvent = AgentStreamEvent;

/**
 * 以 SSE 方式请求 `/api/v1/chat/stream`，逐帧回调解析后的事件。
 *
 * 用原生 fetch 手工切帧：以空行分隔事件，只解析 `data:` 行，忽略 `event:` 行，
 * 因为事件名在 JSON 的 `type` 字段中已有对应值。响应非 2xx 时抛出错误。
 *
 * @param payload - 请求体
 * @param onEvent - 每解析出一个事件时同步调用
 * @param options - 可选的 AbortSignal 与会话 ID 回调
 */
export async function streamChatEvents(
  payload: ChatStreamRequest,
  onEvent: (event: AgentStreamEvent) => void,
  options?: StreamChatOptions
): Promise<void> {
  const response = await fetch("/api/v1/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });

  if (!response.ok || !response.body) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `请求失败（${response.status}）`);
  }

  const conversationId = response.headers.get("X-Conversation-Id");
  if (conversationId && options?.onConversationId) {
    options.onConversationId(conversationId);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of rawEvent.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data) continue;
          try {
            onEvent(JSON.parse(data) as AgentStreamEvent);
          } catch {
            // 单帧解析失败不中断整条流，忽略后继续读取
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/** `streamChatEvents` 的旧名别名，保留供既有调用点使用。 */
export const streamRunEvents = streamChatEvents;
