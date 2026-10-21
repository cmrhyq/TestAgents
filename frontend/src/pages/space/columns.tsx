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
import type { Endpoint, TestRun } from "@/lib/types.ts";
import { formatDate, formatDuration } from "@/lib/format";

export interface EndpointRowHandlers {
  onEdit(endpoint: Endpoint): void;
  onDelete(endpoint: Endpoint): void;
}

export function buildEndpointColumns({ onEdit, onDelete }: EndpointRowHandlers): Column<Endpoint>[] {
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

export function buildTestRunColumns(): Column<TestRun>[] {
  return [
    {
      key: "name",
      header: "名称",
      render: (_, row) => (
        <Link to={`/runs/${row.id}`} className="font-medium text-accent hover:text-accent/80">
          {row.name}
        </Link>
      ),
    },
    {
      key: "status",
      header: "状态",
      render: (_, row) => <StatusBadge status={row.status} />,
    },
    {
      key: "pass_rate",
      header: "通过率",
      render: (_, row) => <PassRateBar passed={row.passed_cases} total={row.total_cases} />,
    },
    {
      key: "total_duration",
      header: "耗时",
      render: (_, row) => (
        <span className="text-sm text-muted-foreground">{formatDuration(row.total_duration)}</span>
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
