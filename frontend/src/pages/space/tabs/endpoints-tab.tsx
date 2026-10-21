import { useRef, useState } from "react";
import { FolderInput, Loader2, Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Input } from "@/components/ui/input.tsx";
import { DataTable } from "@/components/shared/data-table.tsx";
import { ConfirmDeleteDialog } from "@/components/shared/confirm-delete-dialog.tsx";
import { useParseOpenAPI } from "@/hooks/use-workflows.ts";
import { buildEndpointColumns } from "../columns";
import type { Endpoint } from "@/lib/types.ts";

export interface EndpointsTabProps {
  /** 当前空间 id，用于 OpenAPI 导入接口 */
  spaceId: string | number;
  /** 搜索关键字（受控，父组件防抖后发往服务端过滤） */
  keyword: string;
  onKeywordChange(keyword: string): void;
  data: Endpoint[];
  total: number;
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
  page: number;
  pageSize: number;
  onPageChange(page: number): void;
  onAdd(): void;
  onEdit(endpoint: Endpoint): void;
  onDelete(endpoint: Endpoint): void;
}

export function EndpointsTab({
  spaceId,
  keyword,
  onKeywordChange,
  data,
  total,
  loading,
  error = false,
  onRetry,
  page,
  pageSize,
  onPageChange,
  onAdd,
  onEdit,
  onDelete,
}: EndpointsTabProps) {
  const [deleteTarget, setDeleteTarget] = useState<Endpoint | null>(null);

  // 雪花 ID 超过 JS 安全整数范围，必须以 string 透传，禁止 Number() 转换（会丢精度）
  const { mutate: importOpenAPI, isPending: isImporting } = useParseOpenAPI(String(spaceId));
  const fileInputRef = useRef<HTMLInputElement>(null);

  const columns = buildEndpointColumns({
    onEdit,
    onDelete: (endpoint) => setDeleteTarget(endpoint),
  });

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      const formData = new FormData();
      formData.append("file", selected);
      importOpenAPI(formData);
    }
    e.target.value = "";
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索接口…"
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
            className="pl-9"
          />
        </div>
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

      <DataTable
        columns={columns}
        data={data}
        loading={loading}
        error={error}
        onRetry={onRetry}
        emptyText="该空间暂无接口。"
        pagination={{
          page,
          pageSize,
          total,
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
