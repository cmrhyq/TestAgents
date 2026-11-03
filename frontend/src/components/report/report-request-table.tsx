import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import { useReportRequest } from "@/hooks/use-reports.ts";
import { HttpMethodBadge } from "@/components/shared/http-method-badge.tsx";
import type { AgentToolCall } from "@/lib/types.ts";
import { formatDurationMs } from "@/lib/format";
import { cn } from "@/lib/utils.ts";
import { HttpPayloadPanel } from "./http-payload-panel";

/** 状态码读数：2xx 绿、其余红、没有响应码（网络异常/被拦截）用 warning。 */
function statusMeta(call: AgentToolCall): { label: string; className: string } {
  const code = call.http_status_code;
  if (code === null || code === undefined) {
    return { label: "无响应", className: "text-warning" };
  }
  if (code >= 200 && code < 300) {
    return { label: String(code), className: "text-success" };
  }
  return { label: String(code), className: "text-destructive" };
}

function RequestRow({ runId, call }: { runId: string | number; call: AgentToolCall }) {
  const [expanded, setExpanded] = useState(false);

  // 只有展开才拉正文：单条响应体上限 2MB，一轮几十次调用全量拉会把页面撑爆
  const { data: detail, isLoading, isError, refetch } = useReportRequest(runId, call.id, expanded);

  const status = statusMeta(call);

  return (
    <>
      <tr
        className="cursor-pointer border-b border-border-subtle transition-colors hover:bg-muted/40"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <td className="w-10 px-4 py-3">
          <span className="inline-flex items-center text-muted-foreground">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        </td>
        <td className="w-12 px-4 py-3">
          <span className="font-mono text-xs tabular-nums text-muted-foreground">{call.seq}</span>
        </td>
        <td className="px-4 py-3">
          {call.http_method ? (
            <HttpMethodBadge method={call.http_method} />
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </td>
        <td className="max-w-[30rem] px-4 py-3">
          <span
            className="block truncate font-mono text-xs text-muted-foreground"
            title={call.http_url ?? ""}
          >
            {call.http_url ?? "（未发出请求）"}
          </span>
        </td>
        <td className="px-4 py-3">
          <span className={cn("font-mono text-xs font-semibold tabular-nums", status.className)}>
            {status.label}
          </span>
        </td>
        <td className="px-4 py-3">
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {formatDurationMs(call.duration_ms)}
          </span>
        </td>
        <td className="max-w-[16rem] px-4 py-3">
          {call.error_type ? (
            <span className="block truncate text-xs text-destructive" title={call.error_message}>
              {call.error_type}
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </td>
      </tr>

      {expanded && (
        <tr className="border-b border-border-subtle bg-muted/30">
          <td colSpan={7} className="px-4 py-4">
            {isLoading && (
              <div className="flex items-center gap-2 py-6 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                正在加载请求 / 响应正文…
              </div>
            )}

            {!isLoading && isError && (
              <div className="flex items-center gap-3 py-4 text-xs text-destructive">
                正文加载失败
                <button
                  type="button"
                  className="font-medium text-accent hover:underline"
                  onClick={(event) => {
                    // 表格行整体可点，重试按钮不要把行收起
                    event.stopPropagation();
                    refetch();
                  }}
                >
                  重试
                </button>
              </div>
            )}

            {!isLoading && !isError && detail && (
              <HttpPayloadPanel call={detail} bodyLoaded loadingBody={false} />
            )}
          </td>
        </tr>
      )}
    </>
  );
}

interface ReportRequestTableProps {
  runId: string | number;
  requests: AgentToolCall[];
  emptyText?: string;
}

/** 报告详情里的接口清单：一行一次 send_request，点开才拉正文。 */
export function ReportRequestTable({
  runId,
  requests,
  emptyText = "这次执行没有发出任何 HTTP 请求",
}: ReportRequestTableProps) {
  return (
    <div className="w-full overflow-hidden rounded-[4px] border border-border bg-card shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-muted/50">
            <tr>
              <th className="w-10 px-4 py-2.5" />
              <th className="w-12 px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                #
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                方法
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                接口
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                状态
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                耗时
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                错误
              </th>
            </tr>
          </thead>
          <tbody>
            {requests.map((call) => (
              <RequestRow key={String(call.id)} runId={runId} call={call} />
            ))}
            {requests.length === 0 && (
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
