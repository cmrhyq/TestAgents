import { useRef, useState } from "react";
import { FileText, RefreshCw, Search, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import { EmptyState } from "@/components/shared/empty-state.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import {
  useDeleteDocument,
  useDocuments,
  useReindexDocument,
  useSearchKnowledge,
  useUploadDocument,
} from "@/hooks/use-knowledge.ts";
import type { KnowledgeDocument } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  pending: "待索引",
  indexed: "已索引",
  failed: "索引失败",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * 知识库 tab：文档上传 + 切片状态 + 检索预览。
 *
 * 「检索预览」不是装饰——语义检索的效果很难凭空判断，让用户输入一个真实问题
 * 看看能召回什么，比任何说明文字都有用。召回不对就是切片或文档质量问题。
 */
export function KnowledgeTab({ spaceId }: { spaceId: string }) {
  const { data, isLoading, isError, refetch } = useDocuments(spaceId);
  const uploadDocument = useUploadDocument(spaceId);
  const deleteDocument = useDeleteDocument(spaceId);
  const reindexDocument = useReindexDocument(spaceId);
  const search = useSearchKnowledge(spaceId);

  const fileRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");

  const documents = data?.items ?? [];

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) uploadDocument.mutate(file);
    event.target.value = "";
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">
            共 {data?.total ?? 0} 个文档 ·{' '}
            {data?.vector_enabled ? (
              <span className="text-foreground">向量检索已启用</span>
            ) : (
              <span>词法检索（向量库未启用）</span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            刷新
          </Button>
          <Button size="sm" onClick={() => fileRef.current?.click()} disabled={uploadDocument.isPending}>
            <Upload className="mr-2 h-3.5 w-3.5" />
            {uploadDocument.isPending ? "上传中…" : "上传文档"}
          </Button>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
            accept=".md,.txt,.json,.yaml,.yml,.csv,.log"
          />
        </div>
      </div>

      {/* 检索预览 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">检索预览</CardTitle>
          <p className="text-xs text-muted-foreground">
            输入一个真实问题，看看 Agent 能召回哪些片段。
          </p>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && query.trim()) {
                  search.mutate({ query: query.trim() });
                }
              }}
              placeholder="例如：登录接口的鉴权方式是什么"
              className="flex-1 rounded-[3px] border border-border bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary/50 focus:outline-none"
            />
            <Button
              size="sm"
              disabled={!query.trim() || search.isPending}
              onClick={() => search.mutate({ query: query.trim() })}
            >
              <Search className="mr-2 h-3.5 w-3.5" />
              检索
            </Button>
          </div>

          {search.data && (
            <ul className="space-y-1.5">
              {search.data.hits.length === 0 ? (
                <li className="text-xs text-muted-foreground">没有命中任何片段。</li>
              ) : (
                search.data.hits.map((hit, index) => (
                  <li
                    key={`${hit.document}-${hit.seq}-${index}`}
                    className="rounded-[3px] border border-border-subtle px-2.5 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-primary">
                        {hit.document}#{hit.seq}
                      </span>
                      <span className="ml-auto font-mono text-[10px] text-muted-foreground/70">
                        score {hit.score}
                      </span>
                    </div>
                    <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-relaxed text-muted-foreground">
                      {hit.content}
                    </p>
                  </li>
                ))
              )}
            </ul>
          )}
        </CardContent>
      </Card>

      {isError ? (
        <QueryErrorState
          message="文档列表加载失败"
          action={
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-[3px] bg-muted" />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          title="还没有文档"
          description="上传需求文档、接口文档或规范说明，Agent 会用它们回答业务细节。"
        />
      ) : (
        <ul className="divide-y divide-border rounded-[3px] border border-border">
          {documents.map((doc: KnowledgeDocument) => (
            <li key={doc.id} className="flex items-center gap-3 px-3 py-2.5">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />

              <div className="min-w-0 flex-1">
                <span className="block truncate text-sm text-foreground">{doc.filename}</span>
                <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground/70">
                  {formatSize(doc.size)} · {doc.chunk_count} 切片 ·{' '}
                  {doc.index_mode === "vector" ? "向量" : "词法"}
                </span>
                {doc.error && (
                  <span className="mt-0.5 block text-[11px] text-destructive">{doc.error}</span>
                )}
              </div>

              <Badge
                variant={doc.status === "indexed" ? "success" : doc.status === "failed" ? "destructive" : "secondary"}
                className="shrink-0 text-[10px]"
              >
                {STATUS_LABELS[doc.status] ?? doc.status}
              </Badge>

              <button
                type="button"
                aria-label="重新索引"
                onClick={() => reindexDocument.mutate(doc.id)}
                className="shrink-0 rounded-sm p-1 text-muted-foreground transition-colors hover:text-foreground"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                aria-label="删除文档"
                onClick={() => deleteDocument.mutate(doc.id)}
                className="shrink-0 rounded-sm p-1 text-muted-foreground transition-colors hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
