import { Link, NavLink } from "react-router-dom";
import {
  FileText,
  Folder,
  LayoutDashboard,
  PanelLeftClose,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { SpacesSection } from "@/components/layout/spaces-section";
import { ThemeToggle } from "@/components/shared/theme-toggle";

const APP_VERSION = "v0.0.1";
const SIDEBAR_WIDTH = 264;

interface NavItemProps {
  to: string;
  icon: LucideIcon;
  label: string;
}

/** 侧边栏导航项：激活态用浅色块 + 主文字色，不用彩色。 */
function NavItem({ to, icon: Icon, label }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "group flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px] leading-none transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          isActive
            ? "bg-selected font-medium text-foreground"
            : "text-muted-foreground hover:bg-hover hover:text-foreground"
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={cn(
              "h-4 w-4 shrink-0 transition-colors",
              isActive ? "text-accent" : "text-muted-foreground group-hover:text-foreground"
            )}
            strokeWidth={1.75}
          />
          <span className="flex-1 truncate">{label}</span>
        </>
      )}
    </NavLink>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onCollapse: () => void;
}

/** 侧边栏：主导航、空间会话列表、主题与版本。 */
export function Sidebar({ collapsed, onCollapse }: SidebarProps) {
  return (
    <aside
      className={cn(
        "flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-r border-border-subtle bg-sidebar",
        "transition-[width] duration-250 ease-out-expo"
      )}
      style={{ width: collapsed ? 0 : SIDEBAR_WIDTH }}
    >
      <div
        className={cn(
          "flex h-full min-h-0 flex-col overflow-hidden transition-opacity duration-150",
          collapsed ? "pointer-events-none opacity-0" : "opacity-100"
        )}
        inert={collapsed ? true : undefined}
        style={{ minWidth: SIDEBAR_WIDTH }}
      >
        {/* 品牌区 */}
        <div className="flex h-14 shrink-0 items-center gap-2 px-3.5">
          <Link
            to="/dashboard"
            className="flex min-w-0 flex-1 items-center gap-2.5 rounded-md py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            <img src="/favicon.svg" alt="" className="h-6 w-6 shrink-0" aria-hidden="true" />
            <div className="min-w-0">
              <span className="block truncate text-[13px] font-semibold leading-4 text-foreground">
                TestAgents
              </span>
              <span className="block truncate text-[11px] leading-4 text-muted-foreground">
                API 智能测试平台
              </span>
            </div>
          </Link>
          <button
            type="button"
            onClick={onCollapse}
            aria-label="收起侧边栏"
            title="收起侧边栏"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-hover hover:text-foreground"
          >
            <PanelLeftClose className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>

        {/* 主导航 */}
        <nav className="shrink-0 px-2.5 pb-2">
          <p className="px-2.5 pb-1 pt-1 text-[11px] font-medium leading-4 text-muted-foreground">
            工作台
          </p>
          <div className="flex flex-col gap-0.5">
            <NavItem to="/dashboard" icon={LayoutDashboard} label="仪表盘" />
            <NavItem to="/spaces" icon={Folder} label="测试空间" />
            <NavItem to="/reports" icon={FileText} label="测试报告" />
            <NavItem to="/skills" icon={Sparkles} label="技能管理" />
          </div>
        </nav>

        {/* 空间与会话 */}
        <div className="mt-1 flex min-h-0 flex-1 flex-col overflow-hidden border-t border-border-subtle pt-1">
          <SpacesSection />
        </div>

        {/* 底部：主题与版本 */}
        <div className="flex h-11 shrink-0 items-center justify-between border-t border-border-subtle px-2.5">
          <span className="text-[11px] leading-4 text-muted-foreground">{APP_VERSION}</span>
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}
