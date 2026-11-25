/** 初始 hydration 期间的占位骨架：首屏就提供 <main> 地标与页面轮廓。 */
export function AppHydrateFallback() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <div className="hidden w-[264px] shrink-0 border-r border-border-subtle bg-sidebar lg:block" />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="h-12 shrink-0 border-b border-border-subtle" />
        <main id="main-content" className="flex flex-1 flex-col overflow-y-auto">
          <div className="mx-auto w-full max-w-[1400px] flex-1 px-5 py-6 lg:px-8 lg:py-8">
            <div className="h-7 w-40 animate-pulse rounded bg-muted" />
            <div className="mt-2 h-4 w-96 max-w-full animate-pulse rounded bg-muted" />
            <div className="mt-6 h-9 w-full animate-pulse rounded-md bg-muted" />
            <div className="mt-3 rounded-lg border border-border bg-card p-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={index}
                  className="h-8 animate-pulse border-b border-border-subtle bg-muted/40 last:border-b-0"
                />
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
