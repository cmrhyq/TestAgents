import { useState } from "react";
import { Plus, RefreshCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Card, CardContent } from "@/components/ui/card.tsx";
import { EmptyState } from "@/components/shared/empty-state.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import {
  useCreateMemory,
  useDeleteMemory,
  useMemories,
  useUpdateMemory,
} from "@/hooks/use-memories.ts";
import { MEMORY_CATEGORY_LABELS, type MemoryCategory } from "@/lib/types";

const CATEGORIES = Object.entries(MEMORY_CATEGORY_LABELS) as [MemoryCategory, string][];

interface Draft {
  title: string;
  content: string;
  category: MemoryCategory;
}

const EMPTY_DRAFT: Draft = { title: "", content: "", category: "fact" };

/**
 * 记忆 tab：按空间隔离的跨会话记忆。
 *
 * 记忆是**注入 prompt 的**，不是给人看的笔记——所以每条都要能一句话说清、
 * 独立成立。表单强制「标题必填」正是为了逼出这种写法：标题是注入时的要点行。
 */
export function MemoriesTab({ spaceId }: { spaceId: string }) {
  const [category, setCategory] = useState<string | undefined>(undefined);
  const { data, isLoading, isError, refetch } = useMemories(spaceId, category);
  const createMemory = useCreateMemory(spaceId);
  const updateMemory = useUpdateMemory(spaceId);
  const deleteMemory = useDeleteMemory(spaceId);

  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [editingId, setEditingId] = useState<string | null>(null);

  const memories = data?.items ?? [];

  const submit = () => {
    if (!draft.title.trim()) return;

    if (editingId) {
      updateMemory.mutate(
        { id: editingId, payload: draft },
        {
          onSuccess: () => {
            setDraft(EMPTY_DRAFT);
            setEditingId(null);
          },
        }
      );
      return;
    }

    createMemory.mutate(draft, { onSuccess: () => setDraft(EMPTY_DRAFT) });
  };

  const startEdit = (id: string, title: string, content: string, cat: string) => {
    setEditingId(id);
    setDraft({ title, content, category: cat as MemoryCategory });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setCategory(undefined)}
            className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
              category === undefined
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            全部
          </button>
          {CATEGORIES.map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setCategory(value)}
              className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                category === value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-3.5 w-3.5" />
          刷新
        </Button>
      </div>

      {/* 新建 / 编辑表单 */}
      <Card className="bg-surface-primary/30">
        <CardContent className="space-y-2 pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={draft.title}
              onChange={(e) => setDraft((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="要点标题（必填，例如：鉴权方式）"
              className="min-w-[200px] flex-1 rounded-[3px] border border-border bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary/50 focus:outline-none"
            />
            <select
              value={draft.category}
              onChange={(e) =>
                setDraft((prev) => ({ ...prev, category: e.target.value as MemoryCategory }))
              }
              className="rounded-[3px] border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:border-primary/50 focus:outline-none"
            >
              {CATEGORIES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <Button size="sm" onClick={submit} disabled={!draft.title.trim()}>
              <Plus className="mr-2 h-3.5 w-3.5" />
              {editingId ? "保存修改" : "新增记忆"}
            </Button>
            {editingId && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setEditingId(null);
                  setDraft(EMPTY_DRAFT);
                }}
              >
                取消
              </Button>
            )}
          </div>

          <textarea
            value={draft.content}
            onChange={(e) => setDraft((prev) => ({ ...prev, content: e.target.value }))}
            rows={2}
            placeholder="内容（会原样注入 prompt，写清结论即可）"
            className="w-full resize-y rounded-[3px] border border-border bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-primary/50 focus:outline-none"
          />
        </CardContent>
      </Card>

      {isError ? (
        <QueryErrorState
          message="记忆加载失败"
          action={
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-[3px] bg-muted" />
          ))}
        </div>
      ) : memories.length === 0 ? (
        <EmptyState
          title="还没有记忆"
          description="Agent 在执行过程中会自己记录结论，你也可以手动补充。"
        />
      ) : (
        <ul className="space-y-2">
          {memories.map((memory) => (
            <li
              key={memory.id}
              className="group rounded-[3px] border border-border px-3 py-2.5 transition-colors hover:border-primary/40"
            >
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{memory.title}</span>
                    <Badge variant="outline" className="text-[10px]">
                      {memory.category_label}
                    </Badge>
                    {memory.tags.map((tag) => (
                      <span
                        key={tag}
                        className="font-mono text-[10px] text-muted-foreground/70"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                  {memory.content && (
                    <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-relaxed text-muted-foreground">
                      {memory.content}
                    </p>
                  )}
                  <span className="mt-1 block font-mono text-[10px] text-muted-foreground/60">
                    {memory.updated_at.slice(0, 16).replace("T", " ")}
                  </span>
                </div>

                <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <button
                    type="button"
                    onClick={() =>
                      startEdit(String(memory.id), memory.title, memory.content, memory.category)
                    }
                    className="rounded-sm px-1.5 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    aria-label="删除记忆"
                    onClick={() => deleteMemory.mutate(memory.id)}
                    className="rounded-sm p-1 text-muted-foreground transition-colors hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
