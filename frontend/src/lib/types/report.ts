import type { Id, PaginatedResponse } from "./common";
import type { AgentRunBrief, AgentToolCall } from "./agent-run";

/**
 * 一次执行里 HTTP 请求的统计读数。
 *
 * 成功率按 **HTTP 2xx** 算，不是按工具层的 `ok`：`send_request` 对 4xx/5xx
 * 不抛异常，`ok=1` 只代表「请求发出去了」。为了不把 500 显示成成功，
 * 失败拆成两类：`error_count`（拿到响应但非 2xx）与
 * `exception_count`（网络异常/参数错误/被拦截，连响应都没有）。
 */
export interface ReportStat {
  request_count: number;
  /** HTTP 2xx 次数 */
  success_count: number;
  /** 拿到响应但非 2xx 的次数 */
  error_count: number;
  /** 未拿到响应的次数 */
  exception_count: number;
  /** 2xx 占比（0-100） */
  success_rate: number;
  avg_duration_ms: number;
  first_request_at: string | null;
  last_request_at: string | null;
}

/** 报告列表项：一个 run_id 一行（只含发过 send_request 的执行）。 */
export interface Report extends ReportStat {
  run_id: Id;
  title: string;
  status: string;
  mode: string;
  space_id: Id | null;
  run_created_at: string;
}

export type ReportListResponse = PaginatedResponse<Report>;

/**
 * 报告详情：执行摘要 + 统计 + 请求清单（不含正文）。
 *
 * 正文按需拉：`GET /reports/{run_id}/requests/{request_id}`。
 * 单条响应体上限 2MB，一轮 ReAct 几十次调用，整页拉回来就是几十 MB。
 */
export interface ReportDetail {
  run: AgentRunBrief;
  stat: ReportStat;
  requests: AgentToolCall[];
}
