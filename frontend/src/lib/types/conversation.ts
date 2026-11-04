import type { Id, PaginatedResponse } from "./common";

/** 工作模式：agent 自动执行，ask 仅问答，plan 仅出计划。 */
export type ConversationMode = "agent" | "ask" | "plan";

/** 会话。 */
export interface Conversation {
  id: Id;
  space_id: Id | null;
  title: string;
  mode: ConversationMode | string;
  /** 本会话选中的 skill 名；后端存 JSON，接口对外为数组 */
  skill_names: string[];
  environment_id: Id | null;
  status: number;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

/** 会话列表的分页响应。 */
export type ConversationListResponse = PaginatedResponse<Conversation>;

/** 单条会话消息。 */
export interface Message {
  id: Id;
  conversation_id: Id;
  role: "user" | "assistant" | "system";
  content: string;
  meta: string;
  created_at: string;
}

/** 消息列表响应。 */
export interface MessageListResponse {
  items: Message[];
  total: number;
}

/** 会话详情，内嵌消息列表。 */
export interface ConversationDetail extends Conversation {
  messages: Message[];
}

/** 模式的中文标签，供选择器与消息头展示。 */
export const MODE_LABELS: Record<ConversationMode, string> = {
  agent: "执行",
  ask: "问答",
  plan: "计划",
};
