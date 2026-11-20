import { cn } from "@/lib/utils";

interface HttpMethodBadgeProps {
  method: string;
}

/** 各 HTTP 方法的徽章样式。 */
const methodStyles: Record<string, string> = {
  GET: "bg-surface-success text-method-get",
  POST: "bg-surface-accent text-method-post",
  PUT: "bg-surface-warning text-method-put",
  DELETE: "bg-surface-destructive text-method-delete",
  PATCH: "bg-purple-500/10 text-method-patch",
};

const DEFAULT_STYLE = "bg-muted text-muted-foreground";

/** HTTP 方法徽章：等宽定宽，按方法着色。 */
export function HttpMethodBadge({ method }: HttpMethodBadgeProps) {
  const upper = method.toUpperCase();
  const style = methodStyles[upper] ?? DEFAULT_STYLE;

  return (
    <span
      className={cn(
        "inline-flex h-5 w-14 items-center justify-center rounded font-mono text-[11px] font-semibold leading-5",
        style
      )}
    >
      {upper}
    </span>
  );
}
