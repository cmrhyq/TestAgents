import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";
import { ErrorBoundary } from "@/components/shared/error-boundary";

/** 应用骨架：左侧导航 + 顶部面包屑 + 限宽内容区。 */
export function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* 跳过导航直达内容区，供键盘与读屏用户使用 */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:border focus:border-border-strong focus:bg-card focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:shadow-elevated"
      >
        跳到主要内容
      </a>

      <Sidebar collapsed={sidebarCollapsed} onCollapse={() => setSidebarCollapsed(true)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          showExpand={sidebarCollapsed}
          onExpandSidebar={() => setSidebarCollapsed(false)}
        />
        <main id="main-content" className="relative flex flex-1 flex-col overflow-y-auto">
          <div className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col px-5 py-6 lg:px-8 lg:py-8">
            <ErrorBoundary>
              <div
                key={location.pathname}
                className="flex min-h-0 flex-1 flex-col animate-in fade-in-0 slide-in-from-bottom-1 duration-200 ease-out-expo"
              >
                <Outlet />
              </div>
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}
