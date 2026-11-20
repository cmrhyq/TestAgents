import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: ReactNode;
  /** 标题上方的次级说明（可选），不再用作编号标注 */
  annotation?: string;
  description?: ReactNode;
  /** 标题右侧内联内容，如状态徽章 */
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

/** 页头：标题 + 描述 + 右侧操作区，全站统一节奏。 */
export function PageHeader({
  title,
  annotation,
  description,
  meta,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn("flex flex-wrap items-start justify-between gap-x-6 gap-y-3", className)}
    >
      <div className="min-w-0">
        {annotation && (
          <p className="mb-1 text-[12px] leading-4 text-muted-foreground">{annotation}</p>
        )}
        <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <h1 className="truncate text-[20px] font-semibold leading-7 tracking-[-0.01em] text-foreground">
            {title}
          </h1>
          {meta}
        </div>
        {description && (
          <p className="mt-1 max-w-3xl text-[13px] leading-5 text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
