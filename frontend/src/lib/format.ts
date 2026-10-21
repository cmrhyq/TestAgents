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

export function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "--";
  return `${seconds.toFixed(1)}s`;
}

export function formatResponseTime(ms: number): string {
  return `${ms.toFixed(1)} ms`;
}
