import { useState } from "react";
import { MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx";
import { EmptyState } from "@/components/shared/empty-state.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { ConfirmDeleteDialog } from "@/components/shared/confirm-delete-dialog.tsx";
import type { Environment } from "@/lib/types.ts";

export interface EnvironmentsTabProps {
  data: Environment[];
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
  onAdd(): void;
  onEdit(environment: Environment): void;
  onDelete(environment: Environment): void;
}

export function EnvironmentsTab({
  data,
  loading,
  error = false,
  onRetry,
  onAdd,
  onEdit,
  onDelete,
}: EnvironmentsTabProps) {
  const [deleteTarget, setDeleteTarget] = useState<Environment | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">为不同的部署目标管理环境。</p>
        <Button size="sm" onClick={onAdd}>
          <Plus className="mr-2 h-4 w-4" />
          添加环境
        </Button>
      </div>

      {error ? (
        <QueryErrorState
          message="环境列表加载失败"
          action={
            onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                重试
              </Button>
            )
          }
        />
      ) : loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
                <div className="mt-3 h-3 w-full animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : data.length === 0 ? (
        <EmptyState title="暂无环境" description="添加环境以配置不同的基础 URL 和变量。" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.map((env) => (
            <Card key={env.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{env.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    {env.is_default === 1 && (
                      <Badge variant="outline" className="text-xs">
                        默认
                      </Badge>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" aria-label="环境操作">
                          <MoreHorizontal className="h-3.5 w-3.5" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent className="shadow-popover" align="end">
                        <DropdownMenuItem
                          onClick={() => {
                            onEdit(env);
                          }}
                        >
                          <Pencil className="mr-2 h-3.5 w-3.5" />
                          编辑
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => setDeleteTarget(env)}
                        >
                          <Trash2 className="mr-2 h-3.5 w-3.5" />
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="font-mono text-xs text-muted-foreground">{env.base_url}</p>
                {env.description && (
                  <p className="mt-2 text-sm text-muted-foreground">{env.description}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

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
        title="删除环境"
        description={
          <>
            确定要删除环境 <strong>{deleteTarget?.name}</strong> 吗？此操作无法撤销。
          </>
        }
      />
    </div>
  );
}
