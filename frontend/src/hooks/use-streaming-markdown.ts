import { useThrottledValue } from "./use-throttled-value.ts";

interface UseStreamingMarkdownOptions {
  rawText: string;
  isStreaming: boolean;
  /** 流式期间的更新间隔（毫秒），默认 50 */
  throttleMs?: number;
}

/**
 * 流式 Markdown 的展示文本：流式期间按间隔节流更新，流式结束后立即同步最终文本。
 *
 * 节流只降低重解析频率，不改变最终内容。
 */
export function useStreamingMarkdown({
  rawText,
  isStreaming,
  throttleMs = 50,
}: UseStreamingMarkdownOptions) {
  const displayText = useThrottledValue(rawText, isStreaming ? throttleMs : 0);
  return { displayText };
}
