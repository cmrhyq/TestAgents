import type { Id } from "./common";

/** 记忆分类，决定注入 prompt 时的分组与标签。 */
export type MemoryCategory = "fact" | "decision" | "preference" | "issue" | "glossary";

export const MEMORY_CATEGORY_LABELS: Record<MemoryCategory, string> = {
  fact: "事实",
  decision: "决策",
  preference: "偏好",
  issue: "已知问题",
  glossary: "术语",
};

/** 空间内的跨会话记忆条目。 */
export interface SpaceMemory {
  id: Id;
  space_id: Id;
  title: string;
  content: string;
  category: MemoryCategory | string;
  /** 后端计算好的中文分类名，前端直接使用 */
  category_label: string;
  tags: string[];
  source_conversation_id: Id | null;
  created_at: string;
  updated_at: string;
}

/** 记忆列表响应。 */
export interface MemoryListResponse {
  items: SpaceMemory[];
  total: number;
}

/** 新建记忆的请求体。 */
export interface MemoryCreateBody {
  title: string;
  content: string;
  category: MemoryCategory | string;
  tags?: string[];
  source_conversation_id?: Id | null;
}

/** 更新记忆的请求体，字段均可选。 */
export type MemoryUpdateBody = Partial<MemoryCreateBody>;
