/** 详情页加载骨架屏。 */

export function DetailPageSkeleton() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-accent border-t-transparent" />
    </div>
  );
}
