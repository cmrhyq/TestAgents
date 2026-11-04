import type { AgentToolCall, AgentToolCallDetail } from "@/lib/types.ts";
import { formatFileSize, formatJson } from "@/lib/format";
import { cn } from "@/lib/utils.ts";

function JsonBlock({
  label,
  raw,
  destructive,
}: {
  label: string;
  raw: string | null | undefined;
  destructive?: boolean;
}) {
  if (!raw) return null;
  return (
    <div>
      <span
        className={cn("font-medium", destructive ? "text-destructive" : "text-muted-foreground")}
      >
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

/** 判断调用记录是否带有请求与响应正文字段。 */
function hasBody(call: AgentToolCall): call is AgentToolCallDetail {
  return "response_body" in call || "request_body" in call;
}

interface HttpPayloadPanelProps {
  call: AgentToolCall | AgentToolCallDetail;
  /** 请求与响应正文是否已加载；未加载时展示加载入口。 */
  bodyLoaded: boolean;
  loadingBody?: boolean;
  onRequestBody?: () => void;
}

/**
 * 单次工具调用的入参、请求与响应面板。
 *
 * 非 HTTP 工具（如 `query_db`、`read_file`）的 HTTP 字段为空，只展示入参与结果预览。
 */
export function HttpPayloadPanel({
  call,
  bodyLoaded,
  loadingBody = false,
  onRequestBody,
}: HttpPayloadPanelProps) {
  const detail = bodyLoaded && hasBody(call) ? call : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 font-mono text-[11px] text-muted-foreground">
        <span>call_id: {call.call_id || "—"}</span>
        <span>
          第 {call.step_index} 轮 / 第 {call.seq} 次
        </span>
        <span>结果 {call.result_chars} 字符</span>
        {detail && detail.response_size_bytes > 0 && (
          <span>响应体 {formatFileSize(detail.response_size_bytes)}</span>
        )}
        {detail?.response_body_truncated === 1 && (
          <span className="text-warning">响应体超 2MB 已截断入库</span>
        )}
      </div>

      {!bodyLoaded && (
        <div className="flex items-center gap-3 rounded-[3px] border border-dashed border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          <span>请求 / 响应正文未加载（单条最大 2MB，默认不拉取）。</span>
          <button
            type="button"
            className="font-medium text-accent hover:underline disabled:opacity-50"
            onClick={onRequestBody}
            disabled={loadingBody}
          >
            {loadingBody ? "加载中…" : "加载正文"}
          </button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-foreground">请求</h4>
          <div className="space-y-2 text-sm">
            <div>
              <span className="font-medium text-muted-foreground">目标： </span>
              <code className="break-all rounded bg-muted px-1 py-0.5 text-xs">
                {call.http_method ? `${call.http_method} ` : ""}
                {call.http_url ?? "—"}
              </code>
            </div>
            <JsonBlock label="工具入参" raw={detail?.args_json} />
            <JsonBlock label="请求头" raw={detail?.request_headers} />
            <JsonBlock label="查询参数" raw={detail?.request_params} />
            <JsonBlock label="请求体" raw={detail?.request_body} />
          </div>
        </div>

        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-foreground">响应</h4>
          <div className="space-y-2 text-sm">
            <div>
              <span className="font-medium text-muted-foreground">结果： </span>
              <span
                className={cn(
                  "font-mono font-semibold",
                  call.ok === 1 ? "text-success" : "text-destructive"
                )}
              >
                {call.ok === 1 ? "成功" : "失败"}
              </span>
              {call.http_status_code !== null && (
                <span className="ml-2 font-mono text-xs text-muted-foreground">
                  HTTP {call.http_status_code}
                </span>
              )}
            </div>
            <JsonBlock label="响应头" raw={detail?.response_headers} />
            <JsonBlock label="响应体" raw={detail?.response_body} />
            {!detail && <JsonBlock label="结果预览" raw={call.result_preview} />}
            {call.error_type && (
              <JsonBlock label={`错误 (${call.error_type})`} raw={call.error_message} destructive />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
