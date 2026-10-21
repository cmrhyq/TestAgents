import type { Id } from "./common";

/** skill 来源：内置（随代码分发）或空间私有（用户导入）。 */
export type SkillScope = "builtin" | "space";

export interface Skill {
  name: string;
  description: string;
  when_to_use: string;
  version: string;
  scope: SkillScope | string;
  /** 展示用路径，便于排查「这个 skill 从哪加载的」 */
  directory: string;
  /** skill 声明的可用工具，与模式白名单取交集 */
  allowed_tools: string[];
  enabled: boolean;
}

export interface SkillDetail extends Skill {
  /** SKILL.md 正文（不含 frontmatter） */
  body: string;
}

export interface SkillListResponse {
  items: Skill[];
  total: number;
  space_id: string | null;
}

export type SkillId = Id;
