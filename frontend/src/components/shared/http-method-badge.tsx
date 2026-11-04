import { cn } from "@/lib/utils";

interface HttpMethodBadgeProps {
  method: string;
}

/** 各 HTTP 方法的徽章配色。 */
const methodStyles: Record<string, string> = {
  GET: "border-method-get/50 bg-method-get/5 text-method-get",
  POST: "border-method-post/50 bg-method-post/5 text-method-post",
  PUT: "border-method-put/50 bg-method-put/5 text-method-put",
  DELETE: "border-method-delete/50 bg-method-delete/5 text-method-delete",
  PATCH: "border-method-patch/50 bg-method-patch/5 text-method-patch",
};

const DEFAULT_STYLE = "border-border bg-muted text-muted-foreground";

/** HTTP 方法徽章：按方法着色，未收录的方法使用默认样式。 */
export function HttpMethodBadge({ method }: HttpMethodBadgeProps) {
  const upper = method.toUpperCase();
  const style = methodStyles[upper] ?? DEFAULT_STYLE;

  return (
    <span
      className={cn(
        "inline-flex w-16 items-center justify-center rounded-[2px] border font-mono text-xs font-semibold uppercase",
        style
      )}
    >
      {upper}
    </span>
  );
}
