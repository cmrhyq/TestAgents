import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { HttpMethodBadge } from "@/components/shared/http-method-badge.tsx";
import type { AgentToolCall } from "@/lib/types.ts";
import { formatDurationMs } from "@/lib/format";
import { cn } from "@/lib/utils.ts";
import { HttpPayloadPanel } from "./http-payload-panel";

interface ExpandableRowProps {
  call: AgentToolCall;
  bodyLoaded: boolean;
  loadingBody: boolean;
  onRequestBody?: () => void;
}

function ExpandableRow({ call, bodyLoaded, loadingBody, onRequestBody }: ExpandableRowProps) {
  const [expanded, setExpanded] = useState(false);

  const target = call.http_url ?? call.tool_name;
  const failed = call.ok !== 1;

  return (
    <>
      <tr
        className="cursor-pointer border-b border-border transition-colors hover:bg-card"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <td className="px-4 py-3">
          <span className="inline-flex items-center text-muted-foreground">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        </td>
        <td className="px-4 py-3">
          <span className="font-mono text-xs tabular-nums text-muted-foreground">{call.seq}</span>
        </td>
        <td className="px-4 py-3">
          <div className="flex flex-col">
            <span className="font-medium">{call.tool_name || "—"}</span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {call.tool_type}
            </span>
          </div>
        </td>
        <td className="px-4 py-3">
          {call.http_method ? (
            <HttpMethodBadge method={call.http_method} />
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </td>
        <td className="max-w-[26rem] px-4 py-3">
          <span className="block truncate font-mono text-xs text-muted-foreground" title={target}>
            {target}
          </span>
        </td>
        <td className="px-4 py-3">
          <span
            className={cn(
              "font-mono text-[11px] font-semibold",
              failed ? "text-destructive" : "text-success"
            )}
          >
            {failed ? "FAIL" : "OK"}
          </span>
          {call.http_status_code !== null && (
            <span className="ml-2 font-mono text-xs tabular-nums text-muted-foreground">
              {call.http_status_code}
            </span>
          )}
        </td>
        <td className="px-4 py-3">
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {formatDurationMs(call.duration_ms)}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border-subtle bg-muted/30">
          <td colSpan={7} className="px-4 py-4">
            <HttpPayloadPanel
              call={call}
              bodyLoaded={bodyLoaded}
              loadingBody={loadingBody}
              onRequestBody={onRequestBody}
            />
          </td>
        </tr>
      )}
    </>
  );
}

interface ToolCallsTableProps {
  calls: AgentToolCall[];
  /** 请求与响应正文是否已加载 */
  bodyLoaded?: boolean;
  loadingBody?: boolean;
  onRequestBody?: () => void;
  emptyText?: string;
  /** 表头使用失败样式，用于「只看失败」的表格 */
  danger?: boolean;
}

/** 工具调用留痕表格：一行一次调用，展开看完整入参与请求/响应。 */
export function ToolCallsTable({
  calls,
  bodyLoaded = false,
  loadingBody = false,
  onRequestBody,
  emptyText = "暂无工具调用",
  danger = false,
}: ToolCallsTableProps) {
  return (
    <div className="w-full overflow-hidden rounded-lg border-0 shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead
            className={cn("border-b border-border/30", danger ? "bg-destructive/5" : "bg-card")}
          >
            <tr>
              <th className="w-10 px-4 py-3" />
              <th className="w-12 px-4 py-3 text-left font-medium text-muted-foreground">#</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">工具</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">方法</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">目标</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">结果</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">耗时</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((call) => (
              <ExpandableRow
                key={String(call.id)}
                call={call}
                bodyLoaded={bodyLoaded}
                loadingBody={loadingBody}
                onRequestBody={onRequestBody}
              />
            ))}
            {calls.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                  {emptyText}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
