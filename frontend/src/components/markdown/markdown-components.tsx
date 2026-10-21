import type { Components } from "react-markdown";

import { MarkdownCodeBlock } from "./markdown-code-block.tsx";
import { MarkdownMermaidBlock } from "./markdown-mermaid-block.tsx";

const SAFE_PROTOCOL = /^(https?:|mailto:)/i;

/** 创建带 isStreaming 上下文的 ReactMarkdown components 映射。 */
export function createMarkdownComponents(isStreaming: boolean): Components {
  return {
    pre: ({ children }) => <>{children}</>,

    code: ({ className, children }) => {
      const text = String(children).replace(/\n$/, "");
      const match = /language-([\w-]+)/.exec(className ?? "");
      // 无语言标注的 ``` 围栏块，或含换行内容，均按块级代码渲染（保留 ASCII 图/表格对齐）
      const isBlock = Boolean(match) || text.includes("\n");

      if (isBlock) {
        const language = match?.[1] ?? "text";
        if (language === "mermaid") {
          return <MarkdownMermaidBlock code={text} isStreaming={isStreaming} />;
        }
        return <MarkdownCodeBlock code={text} language={language} isStreaming={isStreaming} />;
      }

      return <code className="markdown-inline-code">{children}</code>;
    },

    a: ({ href, children }) => {
      if (!href || !SAFE_PROTOCOL.test(href)) {
        return <span>{children}</span>;
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      );
    },

    img: ({ alt }) => <span className="text-muted-foreground">[{alt || "image"}]</span>,

    table: ({ children }) => (
      <div className="markdown-table-wrapper">
        <table>{children}</table>
      </div>
    ),
  };
}
