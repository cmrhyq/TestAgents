import { useEffect, useId, useState } from "react";
import { useTheme } from "@/hooks/use-theme";

interface MarkdownMermaidBlockProps {
  code: string;
  isStreaming: boolean;
}

interface RenderedMermaid {
  code: string;
  svg: string;
}

let mermaidInitialized = false;
let mermaidTheme: "dark" | "neutral" | null = null;

async function renderMermaid(id: string, code: string, theme: "dark" | "neutral"): Promise<string> {
  const mermaid = (await import("mermaid")).default;

  if (!mermaidInitialized || mermaidTheme !== theme) {
    mermaid.initialize({
      startOnLoad: false,
      theme,
      securityLevel: "strict",
      fontFamily: "inherit",
    });
    mermaidInitialized = true;
    mermaidTheme = theme;
  }

  const { svg } = await mermaid.render(id, code);
  return svg;
}

/**
 * Mermaid 流程图/时序图块：流式期间显示源码，结束后渲染 SVG。
 * 主题跟随 useTheme：暗色夜图 → "dark"，亮色图纸 → "neutral"；主题切换时以 theme 为 key 重渲染。
 */
export function MarkdownMermaidBlock({ code, isStreaming }: MarkdownMermaidBlockProps) {
  const { theme } = useTheme();
  const mermaidTheme = theme === "dark" ? "dark" : "neutral";
  const [rendered, setRendered] = useState<RenderedMermaid | null>(null);
  const rawId = useId().replace(/:/g, "");
  const renderId = `mermaid-${rawId}`;

  useEffect(() => {
    if (isStreaming) return;

    let cancelled = false;

    renderMermaid(renderId, code, mermaidTheme)
      .then((svg) => {
        if (!cancelled) {
          setRendered({ code, svg });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRendered(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [code, isStreaming, renderId, mermaidTheme]);

  const svg = rendered?.code === code ? rendered.svg : null;

  if (isStreaming || !svg) {
    return (
      <pre className="markdown-code-block">
        <code className="language-mermaid">{code}</code>
      </pre>
    );
  }

  return <div className="markdown-mermaid-block" dangerouslySetInnerHTML={{ __html: svg }} />;
}
