import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, MoreHorizontal, Pencil, Plus, Search, Trash2 } from "lucide-react";

import { useSpaces, useDeleteSpace } from "@/hooks/use-spaces.ts";
import { useDebouncedValue } from "@/hooks/use-debounced-value.ts";
import { Button } from "@/components/ui/button.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Input } from "@/components/ui/input.tsx";
import { DataTable } from "@/components/shared/data-table.tsx";
import { PageHeader } from "@/components/layout/page-header.tsx";
import { SpaceFormDialog } from "@/components/space/space-form-dialog.tsx";
import { ConfirmDeleteDialog } from "@/components/shared/confirm-delete-dialog.tsx";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx";
import type { Column } from "@/components/shared/data-table.tsx";
import type { Space } from "@/lib/types.ts";
import { formatDate } from "@/lib/format.ts";

const PAGE_SIZE = 10;

const STATUS_MAP: Record<number, string> = {
  0: "未启用",
  1: "已启用",
};

const STATUS_FILTERS = [
  { value: "all", label: "全部状态", status: undefined as number | undefined },
  { value: "1", label: "已启用", status: 1 },
  { value: "0", label: "未启用", status: 0 },
];

export default function SpacesPage() {
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const debouncedKeyword = useDebouncedValue(keyword, 300);
  const [status, setStatus] = useState<number | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState("all");

  const [formOpen, setFormOpen] = useState(false);
  const [editingSpace, setEditingSpace] = useState<Space | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Space | null>(null);

  const deleteSpace = useDeleteSpace();

  // 过滤条件变化时回到第 1 页
  useEffect(() => {
    setPage(1);
  }, [debouncedKeyword, status]);

  const { data: spacesData, isLoading, isError, refetch } = useSpaces({
    keyword: debouncedKeyword || undefined,
    status,
    page,
    page_size: PAGE_SIZE,
  });

  const statusLabel = useMemo(
    () => STATUS_FILTERS.find((f) => f.value === statusFilter)?.label ?? "全部状态",
    [statusFilter]
  );

  const columns: Column<Space>[] = [
    {
      key: "name",
      header: "名称",
      render: (_, row) => (
        <Link to={`/spaces/${row.id}`} className="font-medium text-accent hover:text-accent/80">
          {row.name}
        </Link>
      ),
    },
    {
      key: "description",
      header: "描述",
      render: (_, row) => (
        <span className="font-mono text-xs text-muted-foreground">{row.description}</span>
      ),
    },
    {
      key: "status",
      header: "状态",
      render: (_, row) => (
        <Badge variant={row.status === 1 ? "success" : "secondary"}>
          {STATUS_MAP[row.status] ?? "未知"}
        </Badge>
      ),
    },
    {
      key: "created_at",
      header: "创建时间",
      render: (_, row) => (
        <span className="font-mono text-xs text-muted-foreground">
          {formatDate(row.created_at)}
        </span>
      ),
    },
    {
      key: "id",
      header: "操作",
      className: "w-12",
      render: (_, row) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="空间操作">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="shadow-popover" align="end">
            <DropdownMenuItem
              onClick={() => {
                setEditingSpace(row);
                setFormOpen(true);
              }}
            >
              <Pencil className="h-3.5 w-3.5" />
              编辑
            </DropdownMenuItem>
            <DropdownMenuItem className="text-destructive" onClick={() => setDeleteTarget(row)}>
              <Trash2 className="h-3.5 w-3.5" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="测试空间"
        annotation="FIG.02 — SPACES"
        description="管理 API 测试空间。"
        actions={
          <Button
            onClick={() => {
              setEditingSpace(null);
              setFormOpen(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            创建空间
          </Button>
        }
      />

      {/* 查询模块 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索空间名称 / 描述…"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            className="pl-9"
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              {statusLabel}
              <ChevronDown className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="shadow-popover" align="end">
            <DropdownMenuRadioGroup
              value={statusFilter}
              onValueChange={(value) => {
                setStatusFilter(value);
                setStatus(STATUS_FILTERS.find((f) => f.value === value)?.status);
              }}
            >
              {STATUS_FILTERS.map((filter) => (
                <DropdownMenuRadioItem key={filter.value} value={filter.value}>
                  {filter.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <DataTable
        columns={columns}
        data={spacesData?.items ?? []}
        loading={isLoading}
        error={isError}
        onRetry={() => refetch()}
        emptyText="暂无空间，创建一个开始使用吧。"
        pagination={{
          page,
          pageSize: PAGE_SIZE,
          total: spacesData?.total ?? 0,
          onChange: setPage,
        }}
      />

      <SpaceFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        space={editingSpace}
      />

      <ConfirmDeleteDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (deleteTarget) {
            deleteSpace.mutate(deleteTarget.id);
            setDeleteTarget(null);
          }
        }}
        title="删除空间"
        description={
          <span>
            确定要删除空间 <strong>{deleteTarget?.name}</strong> 吗？此操作将永久删除所有关联数据，
            包括环境、接口、测试运行、测试用例和报告。{" "}
            <span className="font-semibold text-destructive">此操作无法撤销。</span>
          </span>
        }
        confirmText="删除空间"
      />
    </div>
  );
}
