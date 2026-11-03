import { createHighlighter, type Highlighter } from "shiki";

/** 亮色与暗色双主题，配合 CSS 变量切换。 */
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

/** 判断语言是否启用 Shiki 高亮；`text` 与 ASCII 图保持纯文本以保留对齐。 */
export function shouldHighlightLanguage(language: string): boolean {
  return HIGHLIGHT_LANGS.has(language) && language !== "text";
}

let highlighterPromise: Promise<Highlighter> | null = null;

/** 返回 Shiki 高亮器单例；首次调用触发 wasm 与主题加载。 */
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
