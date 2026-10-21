import { createHighlighter, type Highlighter } from "shiki";

/** 双主题：亮色图纸 github-light / 暗色夜图 github-dark，配合 --shiki-dark 变量切换。 */
const SHIKI_THEMES = {
  light: "github-light",
  dark: "github-dark",
} as const;

const SHIKI_THEME_LIST = [SHIKI_THEMES.light, SHIKI_THEMES.dark] as const;

const SHIKI_LANGS = [
  "json",
  "bash",
  "shell",
  "python",
  "typescript",
  "javascript",
  "yaml",
  "http",
  "markdown",
  "text",
] as const;

const HIGHLIGHT_LANGS = new Set<string>(SHIKI_LANGS);

/** 仅对编程语言启用 Shiki；text/ASCII 图等保持纯文本 pre，避免破坏对齐。 */
export function shouldHighlightLanguage(language: string): boolean {
  return HIGHLIGHT_LANGS.has(language) && language !== "text";
}

let highlighterPromise: Promise<Highlighter> | null = null;

/** Shiki 高亮器单例，一次加载双主题，避免每个代码块重复加载 wasm / 主题。 */
export function getShikiHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: [...SHIKI_THEME_LIST],
      langs: [...SHIKI_LANGS],
    });
  }
  return highlighterPromise;
}

export { SHIKI_THEMES };
