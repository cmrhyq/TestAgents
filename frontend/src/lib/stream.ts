import type { ConversationMode } from "@/lib/types/conversation.ts";

export interface ChatStreamRequest {
  instruction: string;
  conversation_id?: string | number | null;
  space_id?: string | number | null;
  mode?: ConversationMode | string;
  /** 选中的 skill 名，后端会把 SKILL.md 正文注入 system prompt */
  skill_names?: string[];
  /** 指定测试环境；不传则由 Agent 自行 list_environments 选择 */
  environment_id?: string | number | null;
}

export interface StreamChatOptions {
  signal?: AbortSignal;
  /** 首次从响应头 X-Conversation-Id 读取到会话 ID 时触发（用于新建会话回写） */
  onConversationId?: (conversationId: string) => void;
}

/**
 * Agent 流式事件（/chat/stream 统一协议，三种模式共用）。
 *
 * 后端只会发这六种，名字即契约：``start`` / ``text_delta`` / ``tool_call`` /
 * ``tool_result`` / ``final`` / ``error``。
 *
 * 注意 ``final`` 携带**完整回答**，前端不要靠拼接 ``text_delta`` 得到答案——
 * 丢帧或重连会让拼接结果错位，而答案必须准确。
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

/** 兼容旧命名的别名（历史代码里叫 StreamRunEvent）。 */
export type StreamRunEvent = AgentStreamEvent;

/**
 * 以 SSE 方式请求 /api/v1/chat/stream。
 *
 * axios 不适合处理流式响应，这里用原生 fetch + ReadableStream reader 手工切帧。
 * 帧格式固定三行 + 空行（``id:`` / ``event:`` / ``data:``），这里只取 ``data``——
 * ``event`` 名在 JSON 的 ``type`` 字段里也有一份，不需要解析行头。
 *
 * @param payload 请求体
 * @param onEvent 每收到一个事件时触发
 * @param options 可选项：AbortSignal 与会话 ID 回调
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
            // 单帧坏掉不能拖垮整条流：忽略并继续读
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/** 旧名保留，避免既有调用点一次性全改。 */
export const streamRunEvents = streamChatEvents;
