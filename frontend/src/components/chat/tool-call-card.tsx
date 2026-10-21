import { useState } from "react";
import { AlertTriangle, Check, ChevronRight, Loader2, Terminal } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ToolCallRecord } from "@/hooks/use-chat.ts";

/**
 * 工具调用卡片。
 *
 * 为什么要把 args 和返回内容都露出来：Agent 的「过程」比「结论」更值得审。
 * 用户看到「调了 send_request，打的是 prod 域名，返回 401」才能判断结论是否可信；
 * 只给一句「测试完成」等于要求用户盲信。
 */
export function ToolCallCard({ call }: { call: ToolCallRecord }) {
  const [open, setOpen] = useState(false);

  const statusIcon =
    call.status === "running" ? (
      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
    ) : call.status === "ok" ? (
      <Check className="h-3.5 w-3.5 text-success" />
    ) : (
      <AlertTriangle className="h-3.5 w-3.5 text-destructive" />
    );

  const duration = call.status === "running" ? "" : ` · ${call.durationMs}ms`;

  return (
    <div className="rounded-[3px] border border-border bg-background/60">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronRight
          className={cn(
            "h-3 w-3 shrink-0 text-muted-foreground transition-transform duration-150",
            open && "rotate-90"
          )}
        />
        <Terminal className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate font-mono text-xs font-medium text-foreground">{call.name}</span>
        <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-widest text-muted-foreground/70">
          {duration}
        </span>
        {statusIcon}
      </button>

      {open && (
        <div className="space-y-2 border-t border-border-subtle px-2.5 py-2">
          <div>
            <div className="annotation mb-1 text-muted-foreground">ARGS</div>
            <pre className="max-h-40 overflow-auto rounded-[2px] bg-muted/50 p-1.5 font-mono text-[11px] leading-relaxed text-foreground">
              {call.args && Object.keys(call.args).length > 0
                ? JSON.stringify(call.args, null, 2)
                : "（无参数）"}
            </pre>
          </div>

          {call.status !== "running" && (
            <div>
              <div className="annotation mb-1 text-muted-foreground">
                {call.status === "ok" ? "RESULT" : "ERROR"}
              </div>
              <pre
                className={cn(
                  "max-h-60 overflow-auto rounded-[2px] p-1.5 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words",
                  call.status === "ok"
                    ? "bg-muted/50 text-foreground"
                    : "bg-destructive/10 text-destructive"
                )}
              >
                {call.content || "（空）"}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 一组工具调用（按发生顺序）。 */
export function ToolCallList({ calls }: { calls: ToolCallRecord[] }) {
  if (calls.length === 0) return null;

  return (
    <div className="space-y-1.5">
      <div className="annotation text-muted-foreground">TOOL_TRACE · {calls.length}</div>
      {calls.map((call) => (
        <ToolCallCard key={call.id} call={call} />
      ))}
    </div>
  );
}
