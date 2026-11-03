import type { Id, PaginatedResponse } from "./common";

/** 工具分类（与后端 agent_tool_call.tool_type 的 CHECK 约束一一对应） */
export type ToolType =
  | "http"
  | "db"
  | "fs"
  | "exec"
  | "memory"
  | "knowledge"
  | "skill"
  | "search"
  | "other";

/** 执行记录状态。刻意没有 pending——记录在「本轮开始」时才插入，插入即 running。 */
export type AgentRunStatus = "running" | "completed" | "failed" | "cancelled";

/** 一轮 ReAct 对话的执行记录。 */
export interface AgentRun {
  id: Id;
  space_id: Id | null;
  environment_id: Id | null;
  conversation_id: Id | null;
  title: string;
  mode: string;
  trigger_type: string;
  status: AgentRunStatus | string;
  llm_provider: string;
  llm_model: string;
  /** 工具调用总数 */
  tool_call_count: number;
  /** 成功的工具调用数 */
  ok_count: number;
  /** 失败的工具调用数 */
  error_count: number;
  /** 工具调用成功率（0-100 百分比） */
  success_rate: number;
  /** 工具调用平均耗时（毫秒） */
  avg_response_time: number;
  llm_call_count: number;
  total_tokens: number;
  cost_usd: number;
  /** 整轮耗时（毫秒） */
  duration_ms: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export type AgentRunListResponse = PaginatedResponse<AgentRun>;

/** 报告详情里嵌入的执行记录摘要。 */
export interface AgentRunBrief {
  id: Id;
  title: string;
  mode: string;
  status: string;
  llm_provider: string;
  llm_model: string;
  tool_call_count: number;
  ok_count: number;
  error_count: number;
  success_rate: number;
  avg_response_time: number;
  llm_call_count: number;
  total_tokens: number;
  cost_usd: number;
  duration_ms: number;
  started_at: string | null;
  finished_at: string | null;
}

/** 工具调用留痕摘要（不含请求/响应正文）。 */
export interface AgentToolCallBrief {
  id: Id;
  seq: number;
  tool_name: string;
  tool_type: ToolType | string;
  /** 1 成功 / 0 失败 */
  ok: number;
  http_method: string | null;
  http_url: string | null;
  http_status_code: number | null;
  duration_ms: number;
  error_type: string;
  error_message: string;
  created_at: string;
}

/** 工具调用留痕（列表口径，不含正文）。 */
export interface AgentToolCall extends AgentToolCallBrief {
  run_id: Id;
  step_index: number;
  call_id: string;
  result_preview: string;
  result_chars: number;
  /** 1 表示落库时超 2MB 被截断 */
  response_body_truncated: number;
  response_size_bytes: number;
}

/** 工具调用留痕详情（include_body=true 时才有正文字段）。 */
export interface AgentToolCallDetail extends AgentToolCall {
  args_json: string;
  request_headers: string | null;
  request_params: string | null;
  request_body: string | null;
  response_headers: string | null;
  response_body: string | null;
}

export type AgentToolCallListResponse = PaginatedResponse<AgentToolCall>;

/** 执行记录详情（含工具调用摘要列表，不含正文）。 */
export interface AgentRunDetail extends AgentRun {
  tool_calls: AgentToolCallBrief[];
}

/** 清理接口返回。 */
export interface AgentCleanupResult {
  cutoff: string;
  days: number;
  space_id: Id | null;
  dry_run: boolean;
  deleted_runs: number;
  deleted_tool_calls: number;
}
