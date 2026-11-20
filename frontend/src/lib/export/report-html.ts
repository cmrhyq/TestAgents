/**
 * 测试报告的独立 HTML 序列化。
 *
 * 纯字符串拼接，不依赖 React 与任何组件库：产物要能被单独打开、转发、打印成 PDF。
 * 固定浅色配色，不跟随应用主题，否则深色模式下打印出来是一片黑底。
 */
import type { AgentToolCall, AgentToolCallDetail, ReportDetail } from "@/lib/types";
import { formatCost, formatDurationMs, formatJson, formatTokens } from "@/lib/format";

/** 一条请求及其正文；`detail` 为 null 表示正文拉取失败。 */
export interface ReportRequestEntry {
  call: AgentToolCall;
  detail: AgentToolCallDetail | null;
}

export interface ReportExportInput {
  runId: string;
  detail: ReportDetail;
  entries: ReportRequestEntry[];
  exportedAt: Date;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 报告里要精确到秒：`formatDate` 只给日期，看不出一次执行的具体时段。 */
function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  const ymd = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const hms = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  return `${ymd} ${hms}`;
}

/** 状态码语义，与报告页 `statusMeta` 保持同一口径：按 HTTP 2xx 判成败，不认工具层 `ok`。 */
function statusMeta(code: number | null): { label: string; tone: string } {
  if (code === null || code === undefined) return { label: "无响应", tone: "warn" };
  if (code >= 200 && code < 300) return { label: String(code), tone: "ok" };
  return { label: String(code), tone: "err" };
}

/** 结果徽章同样按 HTTP 状态判，`ok=1` 只代表「请求发出去了」。 */
function resultBadge(code: number | null): { label: string; tone: string } {
  if (code === null || code === undefined) return { label: "无响应", tone: "warn" };
  if (code >= 200 && code < 300) return { label: "成功", tone: "ok" };
  return { label: "失败", tone: "err" };
}

/** `agent_run.status` 只有四种取值，直接映射成中文，避免文件里中英混排。 */
const RUN_STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  failed: "已失败",
  running: "运行中",
  cancelled: "已中断",
};

function field(label: string, raw: string | null | undefined, pretty = true): string {
  if (!raw) return "";
  const text = pretty ? formatJson(raw) : raw;
  // `{}` / `[]` 说明后端没记录到内容，占一行反而像有数据
  if (text.trim() === "{}" || text.trim() === "[]") return "";
  return `<div class="field"><span class="lab">${escapeHtml(label)}</span><pre>${escapeHtml(text)}</pre></div>`;
}

function renderEntry(entry: ReportRequestEntry): string {
  const { call, detail } = entry;
  const status = statusMeta(call.http_status_code);
  const result = resultBadge(call.http_status_code);
  const method = call.http_method ?? "—";
  const hasUrl = Boolean(call.http_url);
  const url = call.http_url ?? "未发出请求";

  const requestFields = detail
    ? [
        field("工具入参", detail.args_json),
        field("请求头", detail.request_headers),
        field("查询参数", detail.request_params),
        field("请求体", detail.request_body),
      ].join("")
    : "";

  // 没拿到响应的条目，原因在 error_message 或 result_preview 里；不展示就成了无解释的空白
  const missingResponseReason =
    call.http_status_code === null ? call.error_message || call.result_preview : "";

  const responseFields = detail
    ? [
        field("响应头", detail.response_headers),
        field("响应体", detail.response_body),
        missingResponseReason ? field("异常原因", missingResponseReason) : "",
        call.error_type ? field(`错误（${call.error_type}）`, call.error_message) : "",
      ].join("")
    : field("结果预览", call.result_preview);

  const missingNote = detail
    ? ""
    : `<p class="note warn">正文获取失败，本条只保留清单信息与结果预览。</p>`;

  const truncatedNote =
    detail && detail.response_body_truncated === 1
      ? `<p class="note warn">响应体超过 2MB，入库时已截断，此处展示的是截断后的内容。</p>`
      : "";

  const target = hasUrl ? `${method} ${url}` : "该步骤没有发出 HTTP 请求";

  return `
  <details class="req">
    <summary>
      <span class="seq">#${call.seq}</span>
      <span class="method">${escapeHtml(method)}</span>
      <span class="url">${escapeHtml(url)}</span>
      <span class="code ${status.tone}">${escapeHtml(status.label)}</span>
      <span class="dur">${escapeHtml(formatDurationMs(call.duration_ms))}</span>
    </summary>
    <div class="entry">
      ${missingNote}
      ${truncatedNote}
      <div class="cols">
        <div>
          <h3>请求</h3>
          <div class="field"><span class="lab">目标</span><code>${escapeHtml(target)}</code></div>
          ${requestFields || '<p class="empty">未记录请求细节</p>'}
        </div>
        <div>
          <h3>响应</h3>
          <div class="field">
            <span class="lab">结果</span>
            <span class="badge ${result.tone}">${escapeHtml(result.label)}</span>
            ${
              call.http_status_code === null
                ? ""
                : `<span class="code ${status.tone}">HTTP ${escapeHtml(status.label)}</span>`
            }
          </div>
          ${responseFields || '<p class="empty">响应体为空</p>'}
        </div>
      </div>
    </div>
  </details>`;
}

const STYLE = `
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 32px 24px 48px;
    background: #ffffff;
    color: #000000;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    font-size: 13px;
    line-height: 1.65;
  }
  main { max-width: 1100px; margin: 0 auto; }
  .eyebrow { margin: 0 0 6px; font-size: 11px; font-weight: 500; color: #5d5d5d; letter-spacing: 0.04em; }
  h1 { margin: 0 0 14px; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.35; }
  h2 { margin: 28px 0 10px; font-size: 14px; font-weight: 600; }
  h3 { margin: 0 0 8px; font-size: 12px; font-weight: 600; color: #5d5d5d; }
  .count { margin-left: 6px; font-size: 12px; font-weight: 400; color: #5d5d5d; }
  .meta { display: flex; flex-wrap: wrap; gap: 6px 24px; margin: 0; padding: 12px 0 0; border-top: 1px solid #e6e6e6; }
  .meta div { display: flex; gap: 6px; font-size: 12px; }
  .meta dt { color: #5d5d5d; margin: 0; }
  .meta dd { margin: 0; font-weight: 500; }
  table.stats { width: 100%; border-collapse: collapse; border: 1px solid #e6e6e6; border-radius: 8px; overflow: hidden; }
  table.stats th, table.stats td { padding: 8px 12px; text-align: left; font-size: 12px; border-bottom: 1px solid #f2f2f2; }
  table.stats tr:last-child th, table.stats tr:last-child td { border-bottom: 0; }
  table.stats th { width: 120px; font-weight: 500; color: #5d5d5d; background: #fafafa; }
  table.stats td { font-variant-numeric: tabular-nums; font-weight: 500; }
  .note { margin: 0 0 10px; font-size: 12px; color: #5d5d5d; }
  .note.warn { color: #9a6700; }
  .req { border: 1px solid #e6e6e6; border-radius: 8px; margin-bottom: 8px; overflow: hidden; }
  .req > summary {
    display: flex; align-items: center; gap: 10px; cursor: pointer;
    padding: 8px 12px; background: #fafafa; font-size: 12px; list-style: none;
  }
  .req > summary::-webkit-details-marker { display: none; }
  .req[open] > summary { border-bottom: 1px solid #e6e6e6; }
  .seq { flex: none; width: 44px; color: #5d5d5d; font-variant-numeric: tabular-nums; }
  .method { flex: none; width: 60px; font-weight: 600; }
  .url { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-family: ui-monospace, Menlo, Consolas, monospace; color: #5d5d5d; }
  .code { flex: none; font-variant-numeric: tabular-nums; font-weight: 600; }
  .code.ok { color: #0b8a4d; }
  .code.err { color: #c9302f; }
  .code.warn { color: #9a6700; }
  .dur { flex: none; width: 72px; text-align: right; color: #5d5d5d; font-variant-numeric: tabular-nums; }
  .entry { padding: 12px; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .field { margin-bottom: 8px; }
  .lab { display: block; margin-bottom: 3px; font-size: 11px; font-weight: 500; color: #5d5d5d; }
  .field code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px; word-break: break-all; }
  pre {
    margin: 0; padding: 8px 10px; border: 1px solid #f2f2f2; border-radius: 6px; background: #fafafa;
    font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px; line-height: 1.55;
    white-space: pre-wrap; word-break: break-all; max-height: 460px; overflow: auto;
  }
  .badge { display: inline-block; padding: 0 6px; border-radius: 4px; font-size: 11px; font-weight: 500; }
  .badge.ok { background: #eaf6ef; color: #0b8a4d; }
  .badge.err { background: #fbeeee; color: #c9302f; }
  .badge.warn { background: #fdf6ea; color: #9a6700; }
  .empty { margin: 0; font-size: 11px; color: #8a8a8a; }
  footer { margin-top: 28px; padding-top: 12px; border-top: 1px solid #e6e6e6; font-size: 11px; color: #8a8a8a; }
  @media (max-width: 760px) { .cols { grid-template-columns: 1fr; } }
  @media print {
    body { padding: 0; font-size: 11px; }
    .req { break-inside: avoid; }
    details > *:not(summary) { display: block !important; }
    pre { max-height: none; overflow: visible; }
    @page { margin: 14mm; }
  }
`;

/**
 * 把报告详情与正文渲染成一份自包含 HTML。
 *
 * Args:
 *   input: 执行详情、逐条请求与正文、导出时间。
 *
 * Returns:
 *  完整 HTML 文档字符串，可直接写入 Blob 下载。
 */
export function buildReportHtml({ runId, detail, entries, exportedAt }: ReportExportInput): string {
  const { run, stat } = detail;
  const title = run.title || `执行 ${runId}`;

  const model = [run.llm_provider, run.llm_model].filter(Boolean).join(" / ");

  const metaRows: Array<[string, string]> = [
    ["状态", (RUN_STATUS_LABELS[run.status] ?? run.status) || "—"],
    ["模式", run.mode || "—"],
    // 模型由调用方配置，未配置时给整行会让报告显得像缺数据
    ...(model ? ([["模型", model]] as Array<[string, string]>) : []),
    ["开始", formatDateTime(run.started_at)],
    ["结束", formatDateTime(run.finished_at)],
    ["耗时", formatDurationMs(run.duration_ms)],
    ["Tokens", formatTokens(run.total_tokens)],
    ["成本", formatCost(run.cost_usd)],
  ];

  const statRows: Array<[string, string]> = [
    ["请求数", String(stat.request_count)],
    ["2xx 成功", String(stat.success_count)],
    ["失败（非 2xx）", String(stat.error_count)],
    ["异常（无响应）", String(stat.exception_count)],
    ["成功率", `${stat.success_rate.toFixed(1)}%`],
    ["平均耗时", formatDurationMs(stat.avg_duration_ms)],
  ];

  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} · 测试报告</title>
<style>${STYLE}</style>
</head>
<body>
<main>
  <header>
    <p class="eyebrow">测试报告 · RUN ${escapeHtml(runId)}</p>
    <h1>${escapeHtml(title)}</h1>
    <dl class="meta">
      ${metaRows.map(([k, v]) => `<div><dt>${k}</dt><dd>${escapeHtml(v)}</dd></div>`).join("\n      ")}
    </dl>
  </header>

  <section>
    <h2>统计</h2>
    <table class="stats">
      ${statRows.map(([k, v]) => `<tr><th>${k}</th><td>${escapeHtml(v)}</td></tr>`).join("\n      ")}
    </table>
    <p class="note">成功率按 HTTP 2xx 计算；「异常」指未拿到响应（网络错误 / 参数不合法 / 被拦截）。</p>
  </section>

  <section>
    <h2>接口调用<span class="count">${entries.length} 条</span></h2>
    ${entries.length === 0 ? '<p class="note">这次执行没有发出任何 HTTP 请求。</p>' : entries.map(renderEntry).join("")}
  </section>

  <footer>导出时间 ${escapeHtml(formatDateTime(exportedAt))} · TestAgents</footer>
</main>
</body>
</html>`;
}
