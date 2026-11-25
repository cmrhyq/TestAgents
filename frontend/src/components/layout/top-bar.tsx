import { useLocation } from "react-router-dom";
import { PanelLeftOpen } from "lucide-react";

/** 路由到面包屑文案的映射。 */
const TITLES: Array<{ pattern: RegExp; title: string }> = [
  { pattern: /^\/dashboard$/, title: "仪表盘" },
  { pattern: /^\/spaces\/[^/]+\/chat$/, title: "AI 对话" },
  { pattern: /^\/spaces\/[^/]+$/, title: "空间详情" },
  { pattern: /^\/spaces$/, title: "测试空间" },
  { pattern: /^\/reports\/[^/]+$/, title: "报告详情" },
  { pattern: /^\/reports$/, title: "测试报告" },
  { pattern: /^\/runs\/[^/]+$/, title: "执行详情" },
  { pattern: /^\/skills$/, title: "技能管理" },
];

interface TopBarProps {
  /** 侧边栏收起时在左侧提供展开入口 */
  showExpand: boolean;
  onExpandSidebar: () => void;
}

/** 顶栏：细高、半透明、只承载面包屑与全局入口。 */
export function TopBar({ showExpand, onExpandSidebar }: TopBarProps) {
  const { pathname } = useLocation();
  const title = TITLES.find((t) => t.pattern.test(pathname))?.title ?? "";

  return (
    <header className="sticky top-0 z-40 flex h-12 shrink-0 items-center gap-2 border-b border-border-subtle bg-background/80 px-4 backdrop-blur-md lg:px-6">
      {showExpand && (
        <button
          type="button"
          onClick={onExpandSidebar}
          aria-label="展开侧边栏"
          title="展开侧边栏"
          className="-ml-1 flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-hover hover:text-foreground"
        >
          <PanelLeftOpen className="h-4 w-4" strokeWidth={1.75} />
        </button>
      )}

      <nav aria-label="面包屑" className="flex min-w-0 items-center gap-1.5 text-[13px]">
        <span className="shrink-0 text-muted-foreground">工作台</span>
        <span className="shrink-0 text-muted-foreground/60" aria-hidden="true">
          /
        </span>
        <span className="truncate font-medium text-foreground">{title}</span>
      </nav>
    </header>
  );
}
