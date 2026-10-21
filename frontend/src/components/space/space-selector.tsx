import { Briefcase, Check, ChevronDown } from "lucide-react";

import { useSpaces } from "@/hooks/use-spaces";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { Id, Space } from "@/lib/types";

interface SpaceSelectorProps {
  /** 当前选中的空间 id；为 null/undefined 时显示占位符。 */
  value: Id | null;
  /** 用户从下拉列表选中某项时回调，传入空间 id。 */
  onChange(spaceId: Id): void;
  /** 未选中时的占位文案，默认 "选择工作空间"。 */
  placeholder?: string;
  /** 是否禁用（由父组件控制）。 */
  disabled?: boolean;
}

/** 把不同类型 id 规范成字符串后再比较，避免 number/string 不一致。 */
function toIdString(id: Id | null | undefined): string | null {
  if (id === null || id === undefined) return null;
  return String(id);
}

function findCurrentSpace(spaces: Space[], value: Id | null): Space | undefined {
  const target = toIdString(value);
  if (target === null) return undefined;
  return spaces.find((s) => String(s.id) === target);
}

/**
 * 工作空间选择器（蓝图标注式）。
 *
 * 视觉语言对齐「工业蓝图」：直角描边 chip + mono ``SPACE`` 标注前缀，
 * 与 Composer 的墨线风格统一；下拉项展示空间名 + base_url（mono 副行）。
 */
export function SpaceSelector({
  value,
  onChange,
  placeholder = "选择工作空间",
  disabled,
}: SpaceSelectorProps) {
  const { data, isLoading, isError } = useSpaces({ page_size: 100, status: 1 });
  const spaces = data?.items ?? [];
  const current = findCurrentSpace(spaces, value);
  const isEmpty = !isLoading && !isError && spaces.length === 0;
  const isDisabled = disabled || isError || isEmpty;

  const label = isLoading ? "加载中…" : current?.name ?? placeholder;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={isDisabled}
          className={cn(
            "group inline-flex h-8 items-center gap-2 rounded-[2px] border border-border bg-card px-2.5 shadow-xs transition-colors duration-200 ease-out-expo",
            "hover:border-primary/50 hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-40"
          )}
        >
          {/* mono 标注前缀：SPACE */}
          <span className="hidden items-center gap-1 text-[10px] font-medium uppercase tracking-widest text-muted-foreground sm:flex">
            <Briefcase className="h-3.5 w-3.5 text-primary" />
            Space
          </span>

          <span
            className={cn(
              "max-w-[180px] truncate font-mono text-xs",
              current ? "font-medium text-foreground" : "text-muted-foreground"
            )}
          >
            {label}
          </span>

          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground transition-transform duration-200 ease-out-expo group-data-[state=open]:rotate-180" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-[220px] shadow-popover" align="start">
        <div className="px-2.5 pb-1 pt-2 font-mono text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          Work Spaces
        </div>
        {spaces.length === 0 ? (
          <DropdownMenuItem disabled className="text-muted-foreground">
            暂无可用空间，请先在仪表盘创建
          </DropdownMenuItem>
        ) : (
          spaces.map((space) => {
            const isSelected = current?.id === space.id;
            return (
              <DropdownMenuItem
                key={String(space.id)}
                onClick={() => onChange(space.id)}
                className="flex items-center gap-2.5"
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    isSelected ? "bg-primary" : "bg-muted-foreground/40"
                  )}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-foreground">{space.name}</span>
                  <span className="block truncate font-mono text-[11px] text-muted-foreground">
                    {space.description || "—"}
                  </span>
                </span>
                {isSelected && <Check className="h-3.5 w-3.5 shrink-0 text-primary" />}
              </DropdownMenuItem>
            );
          })
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
