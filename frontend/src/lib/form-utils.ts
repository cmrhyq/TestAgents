/** 表单相关共享工具。 */

/** 判断字符串是否为合法 JSON；空字符串视为未填写，返回 true。 */
export function isValidJson(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed === "") return true;
  try {
    JSON.parse(trimmed);
    return true;
  } catch {
    return false;
  }
}
