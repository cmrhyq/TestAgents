/**
 * 接口标签的前端约束与归一化。
 *
 * 上限与后端 `src/data/constant/endpoint.py` 保持一致；前端先做一次校验是为了即时
 * 提示，真正的约束仍由服务端校验兜底。
 */

/** 单个标签的最大字符数。 */
export const TAG_MAX_LENGTH = 32;

/** 单个接口最多允许的标签数量。 */
export const TAG_MAX_COUNT = 10;

/** 标签中禁止出现的字符，与后端一致。 */
const FORBIDDEN_CHARS = ['"', "\\"];

/**
 * 归一化标签数组：去首尾空白、丢弃空项、按不区分大小写去重。
 *
 * 保留首次出现的写法，`["Auth", "auth"]` 归一为 `["Auth"]`。
 */
export function normalizeTags(values: readonly string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const value of values) {
    const tag = value.trim();
    if (!tag) continue;
    const key = tag.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(tag);
  }

  return result;
}

/**
 * 校验一个待添加的标签。
 *
 * @returns 错误文案；合法时返回 `null`
 */
export function validateTag(raw: string, existing: readonly string[]): string | null {
  const tag = raw.trim();
  if (!tag) return null;

  if (tag.length > TAG_MAX_LENGTH) {
    return `单个标签不能超过 ${TAG_MAX_LENGTH} 个字符`;
  }
  for (const char of FORBIDDEN_CHARS) {
    if (tag.includes(char)) {
      return "标签不能包含双引号或反斜杠";
    }
  }
  if (existing.some((item) => item.toLowerCase() === tag.toLowerCase())) {
    return "该标签已存在";
  }
  if (existing.length >= TAG_MAX_COUNT) {
    return `最多添加 ${TAG_MAX_COUNT} 个标签`;
  }

  return null;
}

/** 把标签数组拼成接口需要的查询参数；空数组返回 `undefined` 表示不过滤。 */
export function toTagsParam(tags: readonly string[]): string | undefined {
  const normalized = normalizeTags(tags);
  return normalized.length > 0 ? normalized.join(",") : undefined;
}
