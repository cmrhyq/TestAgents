import { useStreamingMarkdown } from "@/hooks/use-streaming-markdown.ts";
import { ToolCallList } from "@/components/chat/tool-call-card.tsx";
import { MarkdownRenderer } from "@/components/markdown";
import type { ToolCallRecord } from "@/hooks/use-chat.ts";

/** 用户消息：图纸批注式浅蓝底 + 工程蓝描边。 */
export function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-[4px] border border-primary/40 bg-surface-primary px-4 py-2 text-sm text-foreground">
        {content}
      </div>
    </div>
  );
}

/** Agent 输出：左侧工程蓝墨线 + AGENT 标注 + 分隔虚线。 */
export function AssistantBubble({
  content,
  isStreaming = false,
}: {
  content: string;
  isStreaming?: boolean;
}) {
  return (
    <div className="flex gap-3">
      <div className="w-0.5 shrink-0 self-stretch rounded-full bg-primary/50" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex items-center gap-2">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-primary">
            Agent
          </span>
          <span className="h-px flex-1 border-t border-dashed border-border" aria-hidden="true" />
        </div>
        <MarkdownRenderer content={content} isStreaming={isStreaming} />
      </div>
    </div>
  );
}

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
      <div className="flex items-center gap-2 pl-[14px] font-mono text-sm text-muted-foreground">
        <span className="flex items-center gap-1" aria-hidden="true">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:150ms]" />
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:300ms]" />
        </span>
        <span>处理中</span>
      </div>
    );
  }

  return <AssistantBubble content={displayText} isStreaming={isStreaming} />;
}

/**
 * 一轮进行中的回答：工具轨迹 + 正文 + 错误。
 *
 * 顺序刻意是「先工具后正文」：工具轨迹是**论据**，正文是**结论**，
 * 阅读顺序应该跟人写报告一致。工具卡片默认折叠，避免长轨迹淹没答案。
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
    <div className="flex gap-3">
      <div className="w-0.5 shrink-0 self-stretch rounded-full bg-primary/50" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-2.5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] font-semibold uppercase tracking-widest text-primary">
            Agent
          </span>
          <span className="h-px flex-1 border-t border-dashed border-border" aria-hidden="true" />
          {isStreaming && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
              执行中
            </span>
          )}
        </div>

        {idle && (
          <div className="flex items-center gap-2 font-mono text-sm text-muted-foreground">
            <span className="flex items-center gap-1" aria-hidden="true">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary [animation-delay:300ms]" />
            </span>
            <span>处理中</span>
          </div>
        )}

        {tools.length > 0 && <ToolCallList calls={tools} />}

        {displayText && <MarkdownRenderer content={displayText} isStreaming={isStreaming} />}

        {error && (
          <div className="rounded-[3px] border border-destructive/40 bg-destructive/10 px-2.5 py-2 text-xs text-destructive">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
