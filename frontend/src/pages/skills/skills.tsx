import { useRef, useState } from "react";
import { FileCode2, RefreshCw, Upload, Wrench } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import { PageHeader } from "@/components/layout/page-header.tsx";
import { EmptyState } from "@/components/shared/empty-state.tsx";
import { QueryErrorState } from "@/components/shared/query-error-state.tsx";
import { SpaceSelector } from "@/components/space/space-selector.tsx";
import {
  useImportSkill,
  useSkill,
  useSkills,
  useToggleSkill,
} from "@/hooks/use-skills.ts";
import { cn } from "@/lib/utils";

/**
 * 技能管理页。
 *
 * 默认展示内置技能（不选空间）；选一个空间后会额外列出该空间私有的技能，
 * 同名时空间级覆盖内置。这是「可见范围」而不是「安装位置」——
 * 内置技能属于代码分发，删不掉也不该让人以为能删。
 */
export default function SkillsPage() {
  const [spaceId, setSpaceId] = useState<string | null>(null);
  const [activeName, setActiveName] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useSkills(spaceId);
  const toggleSkill = useToggleSkill(spaceId);
  const importSkill = useImportSkill(spaceId);
  const { data: detail, isLoading: detailLoading } = useSkill(activeName, spaceId);

  const fileRef = useRef<HTMLInputElement>(null);
  const skills = data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="技能管理"
        description="技能是可复用的测试方法论：选中后其正文会注入 system prompt，声明的工具会收窄本轮可用工具。"
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <SpaceSelector value={spaceId} onChange={(id) => setSpaceId(String(id))} placeholder="仅内置技能" />
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            刷新
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => fileRef.current?.click()}
            disabled={importSkill.isPending}
          >
            <Upload className="mr-2 h-3.5 w-3.5" />
            {importSkill.isPending ? "导入中…" : "导入技能包"}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".zip"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) importSkill.mutate(file);
              event.target.value = "";
            }}
          />
        </div>
      </div>

      {isError ? (
        <QueryErrorState
          message="技能列表加载失败"
          action={
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      ) : isLoading ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-[3px] bg-muted" />
          ))}
        </div>
      ) : skills.length === 0 ? (
        <EmptyState
          title="还没有技能"
          description="内置技能应随代码分发在 backend/skills/ 下；也可以导入 zip 包。"
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {skills.map((skill) => {
            const active = activeName === skill.name;
            return (
              <Card
                key={`${skill.scope}:${skill.name}`}
                className={cn(
                  "cursor-pointer transition-colors",
                  active ? "border-primary/60 bg-surface-primary/40" : "hover:border-primary/40",
                  !skill.enabled && "opacity-60"
                )}
                onClick={() => setActiveName(skill.name)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="truncate font-mono text-sm">{skill.name}</CardTitle>
                    <Badge variant="outline" className="shrink-0 text-[10px]">
                      {skill.scope === "builtin" ? "内置" : "空间"}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-2">
                  <p className="line-clamp-3 text-xs leading-relaxed text-muted-foreground">
                    {skill.description}
                  </p>

                  {skill.allowed_tools.length > 0 && (
                    <div className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground/70">
                      <Wrench className="h-3 w-3" />
                      限 {skill.allowed_tools.length} 个工具
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-1">
                    <span className="font-mono text-[10px] text-muted-foreground/60">
                      v{skill.version || "—"}
                    </span>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleSkill.mutate({ name: skill.name, enabled: !skill.enabled });
                      }}
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[10px] transition-colors",
                        skill.enabled
                          ? "border-primary/50 text-primary hover:bg-primary/10"
                          : "border-border text-muted-foreground hover:bg-muted"
                      )}
                    >
                      {skill.enabled ? "已启用" : "已禁用"}
                    </button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {activeName && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="flex items-center gap-2 font-mono text-sm">
                <FileCode2 className="h-4 w-4 text-primary" />
                {activeName}
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setActiveName(null)}>
                关闭
              </Button>
            </div>
            {detail?.when_to_use && (
              <p className="text-xs text-muted-foreground">适用场景：{detail.when_to_use}</p>
            )}
          </CardHeader>
          <CardContent>
            {detailLoading ? (
              <div className="h-24 animate-pulse rounded bg-muted" />
            ) : (
              <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-[3px] bg-muted/40 p-3 font-mono text-[11px] leading-relaxed text-foreground">
                {detail?.body || "（无正文）"}
              </pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
