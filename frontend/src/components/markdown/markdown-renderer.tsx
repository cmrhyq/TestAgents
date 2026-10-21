import { useMemo } from "react";
import ReactMarkdown from "react-markdown";

import { createMarkdownComponents } from "./markdown-components.tsx";
import { preprocessMarkdown } from "./markdown-preprocess.ts";
import { markdownRehypePlugins, markdownRemarkPlugins } from "./markdown-plugins.ts";
import { StreamingCursor } from "./streaming-cursor.tsx";

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

/**
 * LLM Markdown 渲染唯一入口。
 * 安全策略与插件配置见 markdown-plugins.ts / sanitize-schema.ts。
 */
export function MarkdownRenderer({ content, isStreaming = false }: MarkdownRendererProps) {
  const components = useMemo(() => createMarkdownComponents(isStreaming), [isStreaming]);
  const processedContent = useMemo(
    () => preprocessMarkdown(content, isStreaming),
    [content, isStreaming]
  );

  if (!content) {
    return null;
  }

  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={markdownRemarkPlugins}
        rehypePlugins={markdownRehypePlugins}
        components={components}
      >
        {processedContent}
      </ReactMarkdown>
      {isStreaming && <StreamingCursor />}
    </div>
  );
}
