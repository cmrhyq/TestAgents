const rtf = new Intl.RelativeTimeFormat("zh-CN", { numeric: "auto" });

const RELATIVE_UNITS: { unit: Intl.RelativeTimeFormatUnit; ms: number }[] = [
  { unit: "year", ms: 365 * 24 * 60 * 60 * 1000 },
  { unit: "month", ms: 30 * 24 * 60 * 60 * 1000 },
  { unit: "week", ms: 7 * 24 * 60 * 60 * 1000 },
  { unit: "day", ms: 24 * 60 * 60 * 1000 },
  { unit: "hour", ms: 60 * 60 * 1000 },
  { unit: "minute", ms: 60 * 1000 },
  { unit: "second", ms: 1000 },
];

export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const diffMs = date.getTime() - Date.now();
  const absDiffMs = Math.abs(diffMs);

  for (const { unit, ms } of RELATIVE_UNITS) {
    if (absDiffMs >= ms || unit === "second") {
      return rtf.format(Math.round(diffMs / ms), unit);
    }
  }

  return rtf.format(0, "second");
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatJson(raw: string | null | undefined): string {
  if (!raw) return "";
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return date.toLocaleDateString();
}

/**
 * 毫秒耗时格式化。
 *
 * 后端 `duration_ms` 一律是毫秒整数，用它替代老的 `total_duration`（秒）。
 * 分级是为了读数带好看：一次工具调用 45ms 显示成 "0.05s" 毫无信息量。
 */
export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || ms <= 0) return "--";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m${seconds}s`;
}

/** 成本格式化：小额给到 4 位小数，否则 2 位。 */
export function formatCost(usd: number | null | undefined): string {
  if (!usd || usd <= 0) return "$0";
  return usd < 1 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}

/** token 数：千级以上压缩成 12.3k，读数带不被挤爆。 */
export function formatTokens(tokens: number | null | undefined): string {
  if (!tokens || tokens <= 0) return "0";
  if (tokens < 1000) return String(tokens);
  return `${(tokens / 1000).toFixed(1)}k`;
}
