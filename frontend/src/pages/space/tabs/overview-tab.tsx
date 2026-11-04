import { useState } from "react";
import { Folder, FileText, Save } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import { useAgentsMd, useUpdateAgentsMd, useWorkspaceTree } from "@/hooks/use-workspace.ts";
import type { WorkspaceNode } from "@/lib/types";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function TreeNode({ node, depth }: { node: WorkspaceNode; depth: number }) {
  const isDir = node.type === "dir";
  return (
    <li>
      <div
        className="flex items-center gap-1.5 py-0.5 font-mono text-xs"
        style={{ paddingLeft: depth * 12 }}
      >
        {isDir ? (
          <Folder className="h-3.5 w-3.5 shrink-0 text-primary" />
        ) : (
          <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <span className="truncate text-foreground">{node.name}</span>
        {!isDir && (
          <span className="ml-auto shrink-0 text-[10px] text-muted-foreground/70">
            {formatSize(node.size)}
          </span>
        )}
      </div>
      {node.children && node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <TreeNode key={child.path} node={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

/**
 * 概览 tab：工作目录树与空间约定（AGENTS.md）。
 *
 * 两者共同描述「这个空间测什么」，修改 AGENTS.md 后下一轮对话即生效。
 */
export function OverviewTab({ spaceId }: { spaceId: string }) {
  const { data: tree, isLoading: treeLoading } = useWorkspaceTree(spaceId, 3);
  const { data: agentsMd, isLoading: agentsLoading } = useAgentsMd(spaceId);
  const updateAgentsMd = useUpdateAgentsMd(spaceId);

  // edited 为 null 表示尚未编辑，此时展示服务端内容；一旦开始编辑即固定草稿，
  // 避免输入过程中后台重取把内容冲掉。
  const [edited, setEdited] = useState<string | null>(null);

  const serverContent = agentsMd?.content ?? "";
  const draft = edited ?? serverContent;
  const dirty = edited !== null && edited !== serverContent;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">工作目录</CardTitle>
          <p className="text-xs text-muted-foreground">
            这是 Agent 的沙箱：所有文件读写都被限制在这个目录内。
          </p>
        </CardHeader>
        <CardContent>
          {treeLoading ? (
            <div className="space-y-1.5">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-3 w-2/3 animate-pulse rounded bg-muted" />
              ))}
            </div>
          ) : !tree || tree.nodes.length === 0 ? (
            <p className="text-sm text-muted-foreground">目录为空。</p>
          ) : (
            <ul className="max-h-[420px] overflow-auto">
              {tree.nodes.map((node) => (
                <TreeNode key={node.path} node={node} depth={0} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">空间约定（AGENTS.md）</CardTitle>
            <Button
              size="sm"
              variant={dirty ? "default" : "outline"}
              disabled={!dirty || updateAgentsMd.isPending}
              onClick={() => updateAgentsMd.mutate(draft, { onSuccess: () => setEdited(null) })}
            >
              <Save className="mr-2 h-3.5 w-3.5" />
              保存
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            每次对话都会把这份内容注入 system prompt，写完即生效。
          </p>
        </CardHeader>
        <CardContent>
          <textarea
            value={draft}
            onChange={(e) => setEdited(e.target.value)}
            disabled={agentsLoading}
            rows={18}
            spellCheck={false}
            placeholder="例如：&#10;- 鉴权统一走 Bearer token，登录接口返回的 access_token 有效 2 小时&#10;- 涉及金额的接口必须校验精度到分&#10;- 生产环境只读，禁止写操作"
            className="w-full resize-y rounded-[3px] border border-border bg-background px-2.5 py-2 font-mono text-xs leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:border-primary/50 focus:outline-none disabled:opacity-60"
          />
        </CardContent>
      </Card>
    </div>
  );
}
