import { Link } from "react-router-dom";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { HttpMethodBadge } from "@/components/shared/http-method-badge.tsx";
import { PassRateBar } from "@/components/shared/pass-rate-bar.tsx";
import type { Column } from "@/components/shared/data-table.tsx";
import type { AgentRun, Endpoint } from "@/lib/types.ts";
import { formatDate, formatDurationMs } from "@/lib/format";

/** 接口表格行的编辑与删除回调。 */
export interface EndpointRowHandlers {
  onEdit(endpoint: Endpoint): void;
  onDelete(endpoint: Endpoint): void;
}

/** 构建接口表格的列定义。 */
export function buildEndpointColumns({
  onEdit,
  onDelete,
}: EndpointRowHandlers): Column<Endpoint>[] {
  return [
    {
      key: "method",
      header: "方法",
      className: "w-20",
      render: (_, row) => <HttpMethodBadge method={row.method} />,
    },
    {
      key: "path",
      header: "路径",
      render: (_, row) => (
        <span className="font-mono text-xs text-muted-foreground">{row.path}</span>
      ),
    },
    {
      key: "name",
      header: "名称",
      render: (_, row) => <span className="font-medium text-foreground">{row.name}</span>,
    },
    {
      key: "status",
      header: "状态",
      render: (_, row) => <StatusBadge status={row.status === 1 ? "active" : "inactive"} />,
    },
    {
      key: "actions",
      header: "",
      className: "w-10",
      render: (_, row) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" aria-label="接口操作">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="shadow-popover" align="end">
            <DropdownMenuItem
              onClick={() => {
                onEdit(row);
              }}
            >
              <Pencil className="mr-2 h-3.5 w-3.5" />
              编辑
            </DropdownMenuItem>
            <DropdownMenuItem className="text-destructive" onClick={() => onDelete(row)}>
              <Trash2 className="mr-2 h-3.5 w-3.5" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];
}

/** 构建执行记录表格的列定义。 */
export function buildAgentRunColumns(): Column<AgentRun>[] {
  return [
    {
      key: "title",
      header: "执行标题",
      render: (_, row) => (
        <Link to={`/runs/${row.id}`} className="font-medium text-accent hover:text-accent/80">
          {row.title || `执行 ${row.id}`}
        </Link>
      ),
    },
    {
      key: "status",
      header: "状态",
      render: (_, row) => <StatusBadge status={row.status} />,
    },
    {
      key: "tool_call_count",
      header: "工具调用",
      render: (_, row) => (
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {row.tool_call_count}
          {row.error_count > 0 && (
            <span className="ml-1 text-destructive">({row.error_count} 失败)</span>
          )}
        </span>
      ),
    },
    {
      key: "success_rate",
      header: "成功率",
      // 传分子与分母而非百分比：调用数为 0 时渲染占位符，不显示为 0%
      render: (_, row) => <PassRateBar passed={row.ok_count} total={row.tool_call_count} />,
    },
    {
      key: "duration_ms",
      header: "耗时",
      render: (_, row) => (
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {formatDurationMs(row.duration_ms)}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "创建时间",
      render: (_, row) => (
        <span className="text-sm text-muted-foreground">{formatDate(row.created_at)}</span>
      ),
    },
  ];
}
