/** 前端文件下载：Blob -> 临时对象 URL -> 触发 `<a download>`，用完即回收。 */

/** Windows 文件名保留字符，出现在执行标题里会让下载直接失败。 */
const ILLEGAL_FILENAME_CHARS = /[\\/:*?"<>|]/g;

/** C0/C1 控制字符（含换行、制表符）；用 Unicode 类别而非字面量区间，避免正则里出现裸控制字符。 */
const CONTROL_CHARS = /\p{Cc}/gu;

/** 单段文件名的字节上限；多数文件系统限制 255 字节，这里留出时间戳与扩展名的余量。 */
const MAX_FILENAME_BYTES = 180;

function utf8ByteLength(text: string): number {
  return new TextEncoder().encode(text).length;
}

/**
 * 清理文件名：替换非法字符、压缩空白、按 UTF-8 字节截断。
 *
 * Args:
 *   name: 原始文件名（可含中文与标点）。
 *   fallback: 清理后为空时的兜底名。
 *
 * Returns:
 *  可直接用于 `download` 属性的安全文件名。
 */
export function sanitizeFilename(name: string, fallback = "report"): string {
  const cleaned = name
    .replace(CONTROL_CHARS, " ")
    .replace(ILLEGAL_FILENAME_CHARS, "-")
    .replace(/\s+/g, " ")
    .replace(/-{2,}/g, "-")
    .replace(/^[-.\s]+|[-.\s]+$/g, "")
    .trim();

  if (!cleaned) return fallback;

  // 中文一个字 3 字节，按字符数截断会超限，必须按字节逐步收缩
  let result = cleaned;
  while (utf8ByteLength(result) > MAX_FILENAME_BYTES) {
    result = result.slice(0, -1);
  }
  return result || fallback;
}

/** 生成 `20261120-1704` 形式的时间戳，用于文件名去重。 */
export function buildTimestamp(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const ymd = `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`;
  const hm = `${pad(date.getHours())}${pad(date.getMinutes())}`;
  return `${ymd}-${hm}`;
}

/**
 * 触发浏览器下载一段 HTML 文本。
 *
 * Args:
 *   html: 完整 HTML 文档内容。
 *   filename: 下载文件名，调用方需先用 `sanitizeFilename` 清理。
 */
export function downloadHtml(html: string, filename: string): void {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.style.display = "none";

  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  // 立刻 revoke 会让部分浏览器来不及读取，推到下一轮事件循环之后
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
