import { useMemo, useRef, useState } from "react";
import { FolderInput, Loader2, Plus, Search, Tag, X } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Input } from "@/components/ui/input.tsx";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx";
import { DataTable } from "@/components/shared/data-table.tsx";
import { ConfirmDeleteDialog } from "@/components/shared/confirm-delete-dialog.tsx";
import { useParseOpenAPI } from "@/hooks/use-workflows.ts";
import { useEndpointTags, useEndpoints } from "@/hooks/use-endpoints.ts";
import { useDebouncedValue } from "@/hooks/use-debounced-value.ts";
import { toTagsParam } from "@/lib/endpoint-tags.ts";
import { buildEndpointColumns } from "../columns";
import type { Endpoint } from "@/lib/types.ts";

const PAGE_SIZE = 10;

/** `EndpointsTab` 的属性。 */
export interface EndpointsTabProps {
  /** 当前空间 id，用于列表查询、标签聚合与 OpenAPI 导入 */
  spaceId: string | number;
  /** 搜索关键字，受控；防抖在 tab 内完成 */
  keyword: string;
  onKeywordChange(keyword: string): void;
  /** 当前选中的筛选标签，受控 */
  selectedTags: string[];
  onSelectedTagsChange(tags: string[]): void;
  /** 多标签匹配方式：any 命中任一，all 需全部命中 */
  tagsMode: "any" | "all";
  onTagsModeChange(mode: "any" | "all"): void;
  page: number;
  onPageChange(page: number): void;
  onAdd(): void;
  onEdit(endpoint: Endpoint): void;
  onDelete(endpoint: Endpoint): void;
}

/** 接口 tab：搜索、标签筛选、OpenAPI 导入与增删改接口。 */
export function EndpointsTab({
  spaceId,
  keyword,
  onKeywordChange,
  selectedTags,
  onSelectedTagsChange,
  tagsMode,
  onTagsModeChange,
  page,
  onPageChange,
  onAdd,
  onEdit,
  onDelete,
}: EndpointsTabProps) {
  const [deleteTarget, setDeleteTarget] = useState<Endpoint | null>(null);

  // 查询放在 tab 内：只有切到本 tab（组件挂载）时才发请求，避免进详情页就并发拉取
  const debouncedKeyword = useDebouncedValue(keyword, 300);
  const {
    data: endpointsData,
    isLoading,
    isError,
    refetch,
  } = useEndpoints({
    space_id: spaceId,
    keyword: debouncedKeyword || undefined,
    tags: toTagsParam(selectedTags),
    tags_mode: tagsMode,
    page,
    page_size: PAGE_SIZE,
  });
  const { data: tagOptions = [] } = useEndpointTags(spaceId);

  // 雪花 ID 超出 JS 安全整数范围，必须以 string 透传，禁止 Number() 转换以免丢精度
  const { mutate: importOpenAPI, isPending: isImporting } = useParseOpenAPI(String(spaceId));
  const fileInputRef = useRef<HTMLInputElement>(null);

  const columns = useMemo(
    () =>
      buildEndpointColumns({
        onEdit,
        onDelete: (endpoint) => setDeleteTarget(endpoint),
        // 点击表格里的标签即把它加入筛选，省去再从下拉里找一次
        onTagClick: (tag) => {
          if (!selectedTags.includes(tag)) {
            onSelectedTagsChange([...selectedTags, tag]);
          }
        },
      }),
    [onEdit, selectedTags, onSelectedTagsChange]
  );

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      const formData = new FormData();
      formData.append("file", selected);
      importOpenAPI(formData);
    }
    e.target.value = "";
  };

  const toggleTag = (tag: string, checked: boolean) => {
    onSelectedTagsChange(
      checked ? [...selectedTags, tag] : selectedTags.filter((item) => item !== tag)
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索接口名称、路径或标签…"
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
            className="pl-9"
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline" aria-label="按标签筛选">
              <Tag className="mr-2 h-4 w-4" />
              标签
              {selectedTags.length > 0 && (
                <span className="ml-1.5 rounded-md bg-primary px-1 font-mono text-[10px] leading-4 text-primary-foreground">
                  {selectedTags.length}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="max-h-72 w-56 overflow-y-auto">
            {tagOptions.length === 0 ? (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">该空间暂无标签</div>
            ) : (
              tagOptions.map((option) => (
                <DropdownMenuCheckboxItem
                  key={option.name}
                  checked={selectedTags.includes(option.name)}
                  // 阻止选中后菜单关闭，便于连续勾选多个标签
                  onSelect={(event) => event.preventDefault()}
                  onCheckedChange={(checked) => toggleTag(option.name, checked === true)}
                >
                  <span className="flex-1 truncate">{option.name}</span>
                  <span className="ml-2 font-mono text-[11px] tabular-nums text-muted-foreground">
                    {option.count}
                  </span>
                </DropdownMenuCheckboxItem>
              ))
            )}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={onAdd}>
            <Plus className="mr-2 h-4 w-4" />
            添加接口
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.yaml,.yml"
            onChange={handleImportFile}
            className="hidden"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={isImporting}
          >
            {isImporting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <FolderInput className="mr-2 h-4 w-4" />
            )}
            导入
          </Button>
        </div>
      </div>

      {selectedTags.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">
            标签筛选
          </span>
          {selectedTags.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => onSelectedTagsChange(selectedTags.filter((item) => item !== tag))}
              aria-label={`移除筛选 ${tag}`}
              className="inline-flex items-center gap-1 rounded-md border border-accent/40 bg-accent/5 px-1.5 py-0.5 font-mono text-[11px] leading-4 text-accent transition-colors hover:border-accent"
            >
              {tag}
              <X className="h-3 w-3" />
            </button>
          ))}
          <button
            type="button"
            onClick={() => onSelectedTagsChange([])}
            className="text-[11px] text-muted-foreground underline-offset-2 transition-colors hover:text-foreground hover:underline"
          >
            清除全部
          </button>

          {selectedTags.length >= 2 && (
            <label className="ml-1 flex cursor-pointer items-center gap-1.5 text-[11px] text-muted-foreground">
              <input
                type="checkbox"
                checked={tagsMode === "all"}
                onChange={(e) => onTagsModeChange(e.target.checked ? "all" : "any")}
                className="h-3 w-3 accent-primary"
              />
              需同时满足全部标签
            </label>
          )}
        </div>
      )}

      <DataTable
        columns={columns}
        data={endpointsData?.items ?? []}
        loading={isLoading}
        error={isError}
        onRetry={() => refetch()}
        emptyText="该空间暂无接口。"
        pagination={{
          page,
          pageSize: PAGE_SIZE,
          total: endpointsData?.total ?? 0,
          onChange: onPageChange,
        }}
      />

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (deleteTarget) {
            onDelete(deleteTarget);
            setDeleteTarget(null);
          }
        }}
        title="删除接口"
        description={
          <>
            确定要删除接口 <strong>{deleteTarget?.name}</strong> 吗？此操作无法撤销。
          </>
        }
      />
    </div>
  );
}
