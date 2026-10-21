import { useThrottledValue } from "./use-throttled-value.ts";

interface UseStreamingMarkdownOptions {
  rawText: string;
  isStreaming: boolean;
  /** 流式节流间隔（毫秒），默认 50 */
  throttleMs?: number;
}

/**
 * 流式 Markdown 文本 Hook：流式期间节流更新 displayText，结束后立即同步最终文本。
 */
export function useStreamingMarkdown({
  rawText,
  isStreaming,
  throttleMs = 50,
}: UseStreamingMarkdownOptions) {
  const displayText = useThrottledValue(rawText, isStreaming ? throttleMs : 0);
  return { displayText };
}
