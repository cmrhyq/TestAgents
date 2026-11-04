import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  annotation?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

/** 页头：可选的标注编号、标题、描述与右侧操作区。 */
export function PageHeader({
  title,
  annotation,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        {annotation && <div className="annotation mb-1.5 text-primary">{annotation}</div>}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
