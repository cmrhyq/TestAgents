import { Link } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  Folder,
  PanelLeftClose,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { NavLink } from "react-router";
import { SpacesSection } from "@/components/layout/spaces-section";

const APP_VERSION = "v0.0.1";
const SIDEBAR_WIDTH = 250;

interface NavItemProps {
  to: string;
  index: string;
  icon: React.ReactNode;
  label: string;
}

/** 侧边栏导航项，激活态由路由匹配决定。 */
function NavItem({ to, index, icon, label }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 rounded-sm border-l-2 px-3 py-1.5 text-sm transition-colors no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
          isActive
            ? "border-primary bg-surface-primary font-medium text-foreground"
            : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
        )
      }
    >
      {icon}
      <span className="flex-1">{label}</span>
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
        {index}
      </span>
    </NavLink>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

/** 侧边栏：主导航与空间会话列表，宽度可折叠为 0。 */
export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className="flex h-full min-h-0 shrink-0 flex-col overflow-hidden border-r border-border bg-sidebar transition-[width] duration-300 ease-in-out"
      style={{ width: collapsed ? 0 : SIDEBAR_WIDTH }}
    >
      <div
        className={cn(
          "flex h-full min-h-0 min-w-[250px] flex-col overflow-hidden transition-opacity duration-200",
          collapsed ? "pointer-events-none opacity-0" : "opacity-100"
        )}
        inert={collapsed ? true : undefined}
      >
        <div className="flex items-start justify-between gap-2 border-b border-border-subtle px-4 pb-3 pt-4">
          <Link to="/dashboard" className="flex min-w-0 items-start gap-2.5 no-underline">
            {/*<span*/}
            {/*  className="mt-0.5 block h-6 w-6 shrink-0 border-2 border-primary"*/}
            {/*  aria-hidden="true"*/}
            {/*/>*/}
            <img src="/favicon.svg" alt="Logo" className="mt-0.5 h-6 w-6 shrink-0" />
            <div className="min-w-0">
              <span className="block font-display text-sm font-semibold tracking-tight text-foreground">
                LLMTestAgent
              </span>
              <span className="block font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                {APP_VERSION}
              </span>
            </div>
          </Link>
          <button
            type="button"
            onClick={onToggle}
            aria-label="隐藏侧边栏"
            className="shrink-0 rounded-sm p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>

        <div className="px-4 pt-3">
          <span className="annotation text-muted-foreground">NAV_01</span>
        </div>
        <nav className="flex shrink-0 flex-col gap-0.5 px-3 pb-4 pt-1.5">
          <NavItem
            to="/dashboard"
            index="01"
            icon={<LayoutDashboard className="h-4 w-4" />}
            label="仪表盘"
          />
          <NavItem to="/spaces" index="02" icon={<Folder className="h-4 w-4" />} label="测试空间" />
          <NavItem
            to="/skills"
            index="03"
            icon={<Sparkles className="h-4 w-4" />}
            label="技能管理"
          />
          <NavItem to="/reports" index="04" icon={<FileText className="h-4 w-4" />} label="测试报告" />
        </nav>

        <div className="mt-auto flex min-h-0 flex-1 flex-col overflow-hidden border-t border-border">
          <SpacesSection />
        </div>
      </div>
    </aside>
  );
}
