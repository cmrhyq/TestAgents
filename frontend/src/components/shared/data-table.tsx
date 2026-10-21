import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

export interface Column<T> {
  key: string;
  header: string;
  render?: (value: unknown, row: T) => ReactNode;
  className?: string;
}

interface PaginationConfig {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

interface DataTableProps<T extends object> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  /** 请求失败时为 true，显示错误态而非"暂无数据"（避免误导用户）。 */
  error?: boolean;
  /** error 时的提示文案。 */
  errorText?: string;
  /** error 态下的恢复动作（如"重试"按钮）。 */
  onRetry?: () => void;
  emptyText?: string;
  pagination?: PaginationConfig;
}

function getNestedValue(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => {
    if (acc !== null && acc !== undefined && typeof acc === "object") {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

export function DataTable<T extends object>({
  columns,
  data,
  loading = false,
  error = false,
  errorText = "加载失败，请稍后重试",
  onRetry,
  emptyText = "暂无数据",
  pagination,
}: DataTableProps<T>) {
  const totalPages = pagination
    ? Math.max(1, Math.ceil(pagination.total / pagination.pageSize))
    : 1;

  const SKELETON_ROWS = 5;

  return (
    <div className="w-full overflow-hidden rounded-[4px] border border-border bg-card shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-muted/50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground",
                    col.className
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: SKELETON_ROWS }).map((_, rowIdx) => (
                <tr key={`skeleton-${rowIdx.toString()}`} className="border-b border-border-subtle">
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3">
                      <Skeleton className="h-4 w-3/4" />
                    </td>
                  ))}
                </tr>
              ))}

            {!loading && error && (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-sm text-destructive"
                >
                  <div className="flex flex-col items-center gap-3">
                    <span>{errorText}</span>
                    {onRetry && (
                      <button
                        type="button"
                        onClick={onRetry}
                        className="rounded-[2px] border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        重试
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )}

            {!loading && !error && data.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-muted-foreground"
                >
                  {emptyText}
                </td>
              </tr>
            )}

            {!loading &&
              data.map((row, rowIdx) => (
                <tr
                  key={rowIdx.toString()}
                  className="border-b border-border-subtle transition-colors hover:bg-muted/50 last:border-b-0"
                >
                  {columns.map((col) => {
                    const value = getNestedValue(row, col.key);
                    return (
                      <td key={col.key} className={cn("px-4 py-3", col.className)}>
                        {col.render ? col.render(value, row) : String(value ?? "")}
                      </td>
                    );
                  })}
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {pagination && totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <span className="font-mono text-xs text-muted-foreground">
            PAGE {pagination.page} / {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onChange(pagination.page - 1)}
              className={cn(
                "rounded-sm border border-border bg-card px-3 py-1.5 text-sm font-medium transition-colors",
                pagination.page <= 1 ? "cursor-not-allowed opacity-50" : "hover:bg-muted"
              )}
            >
              上一页
            </button>
            <button
              type="button"
              disabled={pagination.page >= totalPages}
              onClick={() => pagination.onChange(pagination.page + 1)}
              className={cn(
                "rounded-sm border border-border bg-card px-3 py-1.5 text-sm font-medium transition-colors",
                pagination.page >= totalPages ? "cursor-not-allowed opacity-50" : "hover:bg-muted"
              )}
            >
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
