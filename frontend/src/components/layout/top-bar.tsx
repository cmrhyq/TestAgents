import { useLocation } from "react-router-dom";
import { ThemeToggle } from "@/components/shared/theme-toggle";

const APP_VERSION = "v0.0.1";

const TITLES: Array<{ pattern: RegExp; title: string }> = [
  { pattern: /^\/dashboard$/, title: "仪表盘" },
  { pattern: /^\/workflows\/chat/, title: "AI 对话" },
  { pattern: /^\/reports\/[^/]+$/, title: "报告详情" },
  { pattern: /^\/reports$/, title: "测试报告" },
  { pattern: /^\/runs\/[^/]+$/, title: "测试运行" },
  { pattern: /^\/spaces$/, title: "测试空间" },
  { pattern: /^\/spaces\/[^/]+$/, title: "空间详情" },
];

/** 全站顶部工具条：图纸标注式面包屑 + 主题切换 + 版本号。 */
export function TopBar() {
  const { pathname } = useLocation();
  const title = TITLES.find((t) => t.pattern.test(pathname))?.title ?? "";

  return (
    <header className="sticky top-0 z-40 flex h-10 shrink-0 items-center justify-between border-b border-border bg-background/85 px-6 backdrop-blur">
      <div className="flex min-w-0 items-center gap-2">
        <span className="font-mono text-[11px] text-muted-foreground">~/</span>
        <span className="truncate font-mono text-[11px] text-foreground">{title}</span>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <ThemeToggle />
        <span className="font-mono text-[11px] text-muted-foreground">{APP_VERSION}</span>
      </div>
    </header>
  );
}
