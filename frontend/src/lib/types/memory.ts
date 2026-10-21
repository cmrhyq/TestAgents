import type { Id } from "./common";

/** 记忆分类。分类决定注入 prompt 时的分组与标签。 */
export type MemoryCategory = "fact" | "decision" | "preference" | "issue" | "glossary";

export const MEMORY_CATEGORY_LABELS: Record<MemoryCategory, string> = {
  fact: "事实",
  decision: "决策",
  preference: "偏好",
  issue: "已知问题",
  glossary: "术语",
};

export interface SpaceMemory {
  id: Id;
  space_id: Id;
  title: string;
  content: string;
  category: MemoryCategory | string;
  /** 后端已算好的中文分类名，前端直接用，避免两处维护映射 */
  category_label: string;
  tags: string[];
  source_conversation_id: Id | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryListResponse {
  items: SpaceMemory[];
  total: number;
}

export interface MemoryCreateBody {
  title: string;
  content: string;
  category: MemoryCategory | string;
  tags?: string[];
  source_conversation_id?: Id | null;
}

export type MemoryUpdateBody = Partial<MemoryCreateBody>;
