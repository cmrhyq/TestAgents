/**
 * 接口标签的只读展示。
 *
 * 表格列宽有限，超出 `max` 的标签折叠为 `+N`，悬停显示完整列表；传入 `onSelect`
 * 时每个标签变为可点击的按钮，用于「点标签 → 回列表按该标签筛选」。
 */
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface EndpointTagListProps {
  /** 标签数组 */
  tags: readonly string[];
  /** 最多展示几个标签，其余折叠，默认 2 */
  max?: number;
  /** 点击标签的回调；不传则渲染为纯展示 */
  onSelect?: (tag: string) => void;
  className?: string;
}

const CHIP_CLASS =
  "inline-flex max-w-[84px] items-center rounded-md border border-border bg-muted/40 px-1.5 py-0.5 font-mono text-[11px] leading-4 text-muted-foreground";

/** 标签徽章列表：空数组显示占位符，超长折叠，可选可点击。 */
export function EndpointTagList({ tags, max = 2, onSelect, className }: EndpointTagListProps) {
  if (tags.length === 0) {
    return <span className={cn("text-xs text-muted-foreground/50", className)}>—</span>;
  }

  const visible = tags.slice(0, max);
  const hidden = tags.slice(max);

  return (
    <div className={cn("flex flex-nowrap items-center gap-1 overflow-hidden", className)}>
      {visible.map((tag, index) =>
        onSelect ? (
          <button
            key={`${tag}-${index}`}
            type="button"
            onClick={() => onSelect(tag)}
            title={tag}
            className={cn(CHIP_CLASS, "transition-colors hover:border-accent/60 hover:text-accent")}
          >
            <span className="truncate">{tag}</span>
          </button>
        ) : (
          <span key={`${tag}-${index}`} title={tag} className={CHIP_CLASS}>
            <span className="truncate">{tag}</span>
          </span>
        )
      )}

      {hidden.length > 0 && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className={cn(CHIP_CLASS, "cursor-default tabular-nums")}>+{hidden.length}</span>
          </TooltipTrigger>
          <TooltipContent>{hidden.join("、")}</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
