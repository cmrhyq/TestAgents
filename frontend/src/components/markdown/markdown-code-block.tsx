import { useEffect, useState } from "react";

import { getShikiHighlighter, shouldHighlightLanguage, SHIKI_THEMES } from "./shiki-highlighter.ts";

interface MarkdownCodeBlockProps {
  code: string;
  language: string;
  isStreaming: boolean;
}

function PlainCodeBlock({ code, language }: { code: string; language: string }) {
  return (
    <pre className="markdown-code-block">
      <code className={`language-${language}`}>{code}</code>
    </pre>
  );
}

/**
 * 代码块：流式期间渲染 plain pre/code；流结束后对编程语言用 Shiki 高亮（双主题）。
 * text/ASCII 图始终用 plain pre，保留换行与空格对齐。
 */
export function MarkdownCodeBlock({ code, language, isStreaming }: MarkdownCodeBlockProps) {
  const usePlain = isStreaming || !shouldHighlightLanguage(language);

  if (usePlain) {
    return <PlainCodeBlock code={code} language={language} />;
  }

  return <HighlightedCodeBlock code={code} language={language} />;
}

function HighlightedCodeBlock({ code, language }: { code: string; language: string }) {
  const [highlightedHtml, setHighlightedHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getShikiHighlighter()
      .then((highlighter) => {
        let html: string;
        try {
          html = highlighter.codeToHtml(code, { lang: language, themes: SHIKI_THEMES });
        } catch {
          html = highlighter.codeToHtml(code, { lang: "text", themes: SHIKI_THEMES });
        }
        if (!cancelled) {
          setHighlightedHtml(html);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHighlightedHtml(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [code, language]);

  if (highlightedHtml === null) {
    return <PlainCodeBlock code={code} language={language} />;
  }

  return (
    <div
      className="markdown-code-block markdown-code-block--highlighted"
      dangerouslySetInnerHTML={{ __html: highlightedHtml }}
    />
  );
}
