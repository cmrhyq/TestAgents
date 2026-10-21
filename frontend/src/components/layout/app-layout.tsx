import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { PanelRightClose } from "lucide-react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* 跳过导航直达内容区（键盘用户，UX #45 Skip Links） */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-[2px] focus:border focus:border-border focus:bg-card focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:shadow-elevated"
      >
        跳到主要内容
      </a>
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(true)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main-content" className="relative flex-1 overflow-y-auto bg-background p-6 lg:p-8">
          {sidebarCollapsed && (
            <button
              type="button"
              onClick={() => setSidebarCollapsed(false)}
              aria-label="展开侧边栏"
              className={cn(
                "fixed left-2 top-2 z-50 flex h-9 w-9 items-center justify-center rounded-sm",
                "border border-border bg-background text-muted-foreground shadow-elevated transition-colors",
                "hover:bg-muted hover:text-foreground",
                "animate-in fade-in-0 zoom-in-95 duration-200"
              )}
            >
              <PanelRightClose className="h-5 w-5" />
            </button>
          )}
          <ErrorBoundary>
            <div
              key={location.pathname}
              className="flex h-full flex-col animate-in fade-in-0 slide-in-from-bottom-1 duration-300 ease-out-expo"
            >
              <Outlet />
            </div>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
