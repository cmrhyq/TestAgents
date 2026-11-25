import { useStreamingMarkdown } from "@/hooks/use-streaming-markdown.ts";
import { ToolCallList } from "@/components/chat/tool-call-card.tsx";
import { MarkdownRenderer } from "@/components/markdown";
import type { ToolCallRecord } from "@/hooks/use-chat.ts";

/** 流式等待指示：三点脉冲。 */
function TypingDots() {
  return (
    <span className="flex items-center gap-1" aria-hidden="true">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground/60" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground/60 [animation-delay:150ms]" />
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground/60 [animation-delay:300ms]" />
    </span>
  );
}

/** 用户消息：右对齐的浅色块。 */
export function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-lg bg-selected px-3.5 py-2 text-[13px] leading-5 text-foreground">
        {content}
      </div>
    </div>
  );
}

/** Agent 输出的标签行，用于区分「谁在说话」。 */
function AssistantLabel({ trailing }: { trailing?: string }) {
  return (
    <div className="mb-1.5 flex items-center gap-2">
      <span className="text-[12px] font-medium leading-4 text-muted-foreground">Agent</span>
      {trailing && <span className="text-[12px] leading-4 text-muted-foreground">{trailing}</span>}
    </div>
  );
}

/** Agent 输出气泡，正文按 Markdown 渲染。 */
export function AssistantBubble({
  content,
  isStreaming = false,
}: {
  content: string;
  isStreaming?: boolean;
}) {
  return (
    <div className="min-w-0">
      <AssistantLabel />
      <MarkdownRenderer content={content} isStreaming={isStreaming} />
    </div>
  );
}

/** 流式回答气泡：首包未到达时显示等待指示。 */
export function StreamingAssistantMessage({
  rawText,
  isStreaming,
}: {
  rawText: string;
  isStreaming: boolean;
}) {
  const { displayText } = useStreamingMarkdown({ rawText, isStreaming });

  if (isStreaming && rawText.length === 0) {
    return (
      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <TypingDots />
        <span>处理中</span>
      </div>
    );
  }

  return <AssistantBubble content={displayText} isStreaming={isStreaming} />;
}

/**
 * 一轮进行中的回答：工具轨迹、正文与错误。
 *
 * 工具轨迹排在正文之前并默认折叠，避免长轨迹淹没答案。
 */
export function StreamingTurn({
  answer,
  tools,
  error,
  isStreaming,
}: {
  answer: string;
  tools: ToolCallRecord[];
  error: string | null;
  isStreaming: boolean;
}) {
  const { displayText } = useStreamingMarkdown({ rawText: answer, isStreaming });

  const idle = isStreaming && answer.length === 0 && tools.length === 0;

  return (
    <div className="min-w-0 space-y-2.5">
      <AssistantLabel trailing={isStreaming ? "执行中" : undefined} />

      {idle && (
        <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
          <TypingDots />
          <span>处理中</span>
        </div>
      )}

      {tools.length > 0 && <ToolCallList calls={tools} />}

      {displayText && <MarkdownRenderer content={displayText} isStreaming={isStreaming} />}

      {error && (
        <div className="rounded-md bg-surface-destructive px-3 py-2 text-[12px] leading-5 text-destructive">
          {error}
        </div>
      )}
    </div>
  );
}
