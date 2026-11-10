import { cn } from "@/lib/utils.ts";

interface AgentModeBadgeProps {
  mode: string;
}

const modeStyles: Record<string, string> = {
  AGENT: "border-method-put/50 bg-method-put/5 text-method-put",
  ASK: "border-method-get/50 bg-method-get/5 text-method-get",
  PLAN: "border-method-patch/50 bg-method-patch/5 text-method-patch",
};

const DEFAULT_STYLE = "border-border bg-muted text-muted-foreground";

export function AgentModeBadge({ mode }: AgentModeBadgeProps) {
  const upper = mode.toUpperCase();
  const style = modeStyles[upper] ?? DEFAULT_STYLE;

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
