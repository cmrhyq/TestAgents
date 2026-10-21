import type { TestResultDetail } from "@/lib/types.ts";
import { formatJson } from "@/lib/format";
import { cn } from "@/lib/utils.ts";

function JsonBlock({ label, raw, destructive }: { label: string; raw: string | null; destructive?: boolean }) {
  if (!raw) return null;
  return (
    <div>
      <span className={cn("font-medium", destructive ? "text-destructive" : "text-muted-foreground")}>
        {label}：
      </span>
      <pre
        className={cn(
          "mt-1 max-h-60 overflow-auto rounded-md border-0 bg-card p-2 text-xs shadow-xs",
          destructive && "border-thin border-destructive/20 bg-destructive/5 text-destructive"
        )}
      >
        {formatJson(raw)}
      </pre>
    </div>
  );
}

/** 请求 / 响应详情面板（可展开行内的两栏内容）。 */
export function HttpPayloadPanel({ result }: { result: TestResultDetail }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-foreground">请求</h4>
        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium text-muted-foreground">URL： </span>
            <code className="break-all rounded bg-muted px-1 py-0.5 text-xs">
              {result.request_url}
            </code>
          </div>
          {result.request_headers && result.request_headers !== "{}" && (
            <JsonBlock label="请求头" raw={result.request_headers} />
          )}
          {result.query_params && <JsonBlock label="查询参数" raw={result.query_params} />}
          {result.request_body && <JsonBlock label="请求体" raw={result.request_body} />}
        </div>
      </div>

      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-foreground">响应</h4>
        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium text-muted-foreground">状态码： </span>
            <span
              className={cn(
                "font-mono font-semibold",
                result.response_status_code && result.response_status_code < 400
                  ? "text-success"
                  : "text-destructive"
              )}
            >
              {result.response_status_code ?? "N/A"}
            </span>
          </div>
          {result.response_headers && result.response_headers !== "{}" && (
            <JsonBlock label="响应头" raw={result.response_headers} />
          )}
          {result.response_body && <JsonBlock label="响应体" raw={result.response_body} />}
          {result.error_message && <JsonBlock label="错误" raw={result.error_message} destructive />}
          {result.retry_count > 0 && (
            <div>
              <span className="font-medium text-muted-foreground">重试次数： </span>
              <span>{result.retry_count}</span>
            </div>
          )}
          {result.started_at && result.finished_at && (
            <div>
              <span className="font-medium text-muted-foreground">时间： </span>
              <span className="text-xs text-muted-foreground">
                {result.started_at} ~ {result.finished_at}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
