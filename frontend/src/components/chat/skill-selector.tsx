import { Check, ChevronDown, Sparkles } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu.tsx";
import { useSkills } from "@/hooks/use-skills.ts";
import { cn } from "@/lib/utils";

export interface SkillSelectorProps {
  spaceId: string | null;
  selected: string[];
  onToggle(name: string): void;
  disabled?: boolean;
}

/**
 * 技能多选器。
 *
 * 一个刻意的取舍：**只列 enabled 的 skill**。禁用的 skill 出现在可选列表里会让人
 * 以为选了就生效，而实际后端会跳过它——列表只呈现「当下真的可用」的东西。
 */
export function SkillSelector({ spaceId, selected, onToggle, disabled }: SkillSelectorProps) {
  const { data, isLoading } = useSkills(spaceId);
  const skills = (data?.items ?? []).filter((skill) => skill.enabled);

  const label = selected.length === 0 ? "未选技能" : `已选 ${selected.length} 个技能`;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled || isLoading}
          className={cn(
            "flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground shadow-xs transition-colors hover:bg-muted hover:text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
            (disabled || isLoading) && "cursor-not-allowed opacity-40"
          )}
        >
          <Sparkles className="h-3.5 w-3.5" />
          {label}
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-72 shadow-popover">
        <DropdownMenuLabel className="annotation text-muted-foreground">
          SKILLS · 注入 system prompt
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {skills.length === 0 ? (
          <div className="px-2 py-4 text-center text-xs text-muted-foreground">
            {isLoading ? "加载中…" : "当前空间没有可用技能"}
          </div>
        ) : (
          skills.map((skill) => {
            const active = selected.includes(skill.name);
            return (
              <DropdownMenuItem
                key={`${skill.scope}:${skill.name}`}
                // 多选下拉不自动关闭菜单：onSelect 阻止默认关闭
                onSelect={(event) => {
                  event.preventDefault();
                  onToggle(skill.name);
                }}
                className="items-start gap-2"
              >
                <span
                  className={cn(
                    "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-[2px] border",
                    active ? "border-primary bg-primary text-primary-foreground" : "border-border"
                  )}
                  aria-hidden="true"
                >
                  {active && <Check className="h-3 w-3" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate font-mono text-xs text-foreground">{skill.name}</span>
                    <span className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
                      {skill.scope === "builtin" ? "内置" : "空间"}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                    {skill.when_to_use || skill.description}
                  </span>
                </span>
              </DropdownMenuItem>
            );
          })
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
