import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

/** 表格列定义。 */
export interface Column<T> {
  /** 行数据的取值路径，支持 `a.b` 形式的嵌套键 */
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
  /** 请求失败时为 true，显示错误态而非空态 */
  error?: boolean;
  /** 错误态提示文案 */
  errorText?: string;
  /** 错误态下的恢复动作，如重试 */
  onRetry?: () => void;
  emptyText?: string;
  /** 自定义空态（图标 + 标题 + 操作），优先于 emptyText */
  emptyState?: ReactNode;
  /** 表格的可访问名称，供读屏识别 */
  ariaLabel?: string;
  /** 固定列宽，避免空态/加载态下列宽重排 */
  fixedLayout?: boolean;
  pagination?: PaginationConfig;
  /** 整行可点击（如进入详情）；触发时同时支持键盘 Enter */
  onRowClick?: (row: T) => void;
}

function getNestedValue(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => {
    if (acc !== null && acc !== undefined && typeof acc === "object") {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

const pageButtonClass =
  "inline-flex h-7 items-center rounded-md border border-border bg-card px-2.5 text-[12px] font-medium text-foreground transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-card";

/** 通用表格：加载骨架、错误态、空态与分页。 */
export function DataTable<T extends object>({
  columns,
  data,
  loading = false,
  error = false,
  errorText = "加载失败，请稍后重试",
  onRetry,
  emptyText = "暂无数据",
  emptyState,
  ariaLabel,
  fixedLayout = false,
  pagination,
  onRowClick,
}: DataTableProps<T>) {
  const totalPages = pagination
    ? Math.max(1, Math.ceil(pagination.total / pagination.pageSize))
    : 1;

  const SKELETON_ROWS = 6;

  return (
    <div className="w-full overflow-hidden rounded-lg border border-border bg-card">
      <div className="overflow-x-auto">
        <table
          className={cn("w-full border-collapse text-[13px]", fixedLayout && "table-fixed")}
          aria-label={ariaLabel}
        >
          <thead>
            <tr className="border-b border-border bg-muted">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    "whitespace-nowrap px-3 py-2 text-left text-[12px] font-medium leading-5 text-muted-foreground",
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
                    <td key={col.key} className="px-3 py-2.5">
                      <Skeleton className="h-3.5 w-3/4" />
                    </td>
                  ))}
                </tr>
              ))}

            {!loading && error && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-14 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <span className="text-[13px] text-destructive">{errorText}</span>
                    {onRetry && (
                      <button type="button" onClick={onRetry} className={pageButtonClass}>
                        重试
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )}

            {!loading && !error && data.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-3 py-14">
                  {emptyState ?? (
                    <p className="text-center text-[13px] text-muted-foreground">{emptyText}</p>
                  )}
                </td>
              </tr>
            )}

            {!loading &&
              data.map((row, rowIdx) => (
                <tr
                  key={rowIdx.toString()}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onRowClick(row);
                          }
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                  className={cn(
                    "border-b border-border-subtle transition-colors last:border-b-0",
                    onRowClick &&
                      "cursor-pointer hover:bg-hover focus-visible:bg-hover focus-visible:outline-none"
                  )}
                >
                  {columns.map((col) => {
                    const value = getNestedValue(row, col.key);
                    return (
                      <td
                        key={col.key}
                        className={cn("px-3 py-2.5 leading-5", col.className)}
                      >
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
        <div className="flex items-center justify-between border-t border-border px-3 py-2">
          <span className="text-[12px] leading-5 text-muted-foreground">
            第 {pagination.page} / {totalPages} 页 · 共 {pagination.total} 条
          </span>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onChange(pagination.page - 1)}
              className={pageButtonClass}
            >
              上一页
            </button>
            <button
              type="button"
              disabled={pagination.page >= totalPages}
              onClick={() => pagination.onChange(pagination.page + 1)}
              className={pageButtonClass}
            >
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
