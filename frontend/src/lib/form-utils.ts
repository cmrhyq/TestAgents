/** 表单相关共享工具。 */

/** 判断字符串是否为合法 JSON（空字符串视为合法，表示"未填写"）。 */
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
