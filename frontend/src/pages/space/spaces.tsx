import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronDown,
  FolderPlus,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  SearchX,
  Trash2,
} from "lucide-react";

import { useSpaces, useDeleteSpace } from "@/hooks/use-spaces.ts";
import { useDebouncedValue } from "@/hooks/use-debounced-value.ts";
import { useDocumentTitle } from "@/hooks/use-document-title.ts";
import { Button } from "@/components/ui/button.tsx";
import { Input } from "@/components/ui/input.tsx";
import { DataTable } from "@/components/shared/data-table.tsx";
import { StatusBadge } from "@/components/shared/status-badge.tsx";
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip.tsx";
import type { Column } from "@/components/shared/data-table.tsx";
import type { Space } from "@/lib/types.ts";
import { formatIsoDate } from "@/lib/format.ts";

const PAGE_SIZE = 10;

const STATUS_FILTERS = [
  { value: "all", label: "全部状态", status: undefined as number | undefined },
  { value: "1", label: "已启用", status: 1 },
  { value: "0", label: "未启用", status: 0 },
];

interface SpaceActionsProps {
  space: Space;
  onEdit: (space: Space) => void;
  onDelete: (space: Space) => void;
}

/** 行尾操作菜单：带 tooltip，菜单展开时隐藏提示避免重叠。 */
function SpaceActions({ space, onEdit, onDelete }: SpaceActionsProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <Tooltip open={menuOpen ? false : undefined}>
      <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="空间操作">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <DropdownMenuContent className="shadow-popover" align="end">
          <DropdownMenuItem onClick={() => onEdit(space)}>
            <Pencil className="h-3.5 w-3.5" />
            编辑
          </DropdownMenuItem>
          <DropdownMenuItem className="text-destructive" onClick={() => onDelete(space)}>
            <Trash2 className="h-3.5 w-3.5" />
            删除
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <TooltipContent>空间操作</TooltipContent>
    </Tooltip>
  );
}

/** 空间列表页：搜索、状态筛选、创建与删除。 */
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

  useDocumentTitle("测试空间");

  // 区分「没有数据」与「筛选后没有结果」，空态文案与操作据此切换
  const hasFilters = Boolean(debouncedKeyword.trim()) || status !== undefined;
  const clearFilters = () => {
    setKeyword("");
    setStatus(undefined);
    setStatusFilter("all");
    setPage(1);
  };

  const {
    data: spacesData,
    isLoading,
    isError,
    refetch,
  } = useSpaces({
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
      // 名称与描述合并为一列：整块可点，描述不再是"看得见点不动"的死区
      key: "name",
      header: "名称",
      className: "w-[46%]",
      render: (_, row) => (
        <Link
          to={`/spaces/${row.id}`}
          className="block rounded-sm px-1 py-0.5 transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        >
          <span className="block truncate font-medium text-foreground">{row.name}</span>
          {row.description && (
            <span className="mt-0.5 block truncate text-[12px] leading-4 text-muted-foreground">
              {row.description}
            </span>
          )}
        </Link>
      ),
    },
    {
      key: "status",
      header: "状态",
      className: "w-[112px]",
      render: (_, row) => <StatusBadge status={row.status === 1 ? "active" : "inactive"} />,
    },
    {
      key: "created_at",
      header: "创建时间",
      className: "w-[136px]",
      render: (_, row) => (
        <span className="block text-right tabular-nums text-[12px] text-muted-foreground">
          {formatIsoDate(row.created_at)}
        </span>
      ),
    },
    {
      key: "id",
      header: "操作",
      className: "w-14 text-right",
      render: (_, row) => (
        <SpaceActions
          space={row}
          onEdit={(space) => {
            setEditingSpace(space);
            setFormOpen(true);
          }}
          onDelete={setDeleteTarget}
        />
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="测试空间"
        description="每个空间是一个独立的测试工作区：环境、接口、知识库与执行记录相互隔离。"
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-[320px]">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索空间名称或描述"
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
            className="pl-8"
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="default">
              {statusLabel}
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="shadow-popover" align="end">
            <DropdownMenuRadioGroup
              value={statusFilter}
              onValueChange={(value) => {
                setStatusFilter(value);
                setStatus(STATUS_FILTERS.find((f) => f.value === value)?.status);
                setPage(1);
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

        <div className="ml-auto flex items-center gap-2">
          <Button
            onClick={() => {
              setEditingSpace(null);
              setFormOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            创建空间
          </Button>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={spacesData?.items ?? []}
        loading={isLoading}
        error={isError}
        onRetry={() => refetch()}
        ariaLabel="测试空间列表"
        fixedLayout
        emptyText="暂无空间，创建一个开始使用吧。"
        emptyState={
          <div className="flex flex-col items-center gap-3">
            <div className="text-muted-foreground">
              {hasFilters ? (
                <SearchX className="h-9 w-9" strokeWidth={1.5} />
              ) : (
                <FolderPlus className="h-9 w-9" strokeWidth={1.5} />
              )}
            </div>
            <div className="space-y-1 text-center">
              <p className="text-[14px] font-medium text-foreground">
                {hasFilters ? "没有找到匹配的空间" : "暂无空间，创建一个开始使用吧"}
              </p>
              <p className="text-[12px] text-muted-foreground">
                {hasFilters
                  ? "试试其他关键词，或清除筛选查看全部空间。"
                  : "空间之间的环境、接口与执行记录相互隔离。"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {hasFilters && (
                <Button variant="outline" onClick={clearFilters}>
                  清除筛选
                </Button>
              )}
              <Button
                onClick={() => {
                  setEditingSpace(null);
                  setFormOpen(true);
                }}
              >
                <Plus className="h-4 w-4" />
                创建空间
              </Button>
            </div>
          </div>
        }
        pagination={{
          page,
          pageSize: PAGE_SIZE,
          total: spacesData?.total ?? 0,
          onChange: setPage,
        }}
      />

      <SpaceFormDialog open={formOpen} onOpenChange={setFormOpen} space={editingSpace} />

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
