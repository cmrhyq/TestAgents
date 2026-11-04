import type { Id } from "./common";

/** skill 来源：内置随代码分发，空间私有由用户导入。 */
export type SkillScope = "builtin" | "space";

/** skill 元信息。 */
export interface Skill {
  name: string;
  description: string;
  when_to_use: string;
  version: string;
  scope: SkillScope | string;
  /** 展示用路径，用于排查 skill 的加载位置 */
  directory: string;
  /** skill 声明的可用工具，与模式白名单取交集 */
  allowed_tools: string[];
  enabled: boolean;
}

/** skill 详情，附带 SKILL.md 正文。 */
export interface SkillDetail extends Skill {
  /** SKILL.md 正文，不含 frontmatter */
  body: string;
}

/** skill 列表响应。 */
export interface SkillListResponse {
  items: Skill[];
  total: number;
  space_id: string | null;
}

/** skill 标识。 */
export type SkillId = Id;
