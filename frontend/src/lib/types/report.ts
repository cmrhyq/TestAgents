import type { Id, PaginatedResponse } from "./common";
import type { AgentRunBrief, AgentToolCallDetail } from "./agent-run";

/** 报告文件的元信息。 */
export interface Report {
  id: Id;
  run_id: Id;
  format: string;
  file_size: number;
  generated_at: string;
  /** 所属执行记录的标题，由后端 join 得到，非报告自身字段 */
  run_title: string;
}

/** 报告列表的分页响应。 */
export type ReportListResponse = PaginatedResponse<Report>;

/**
 * 报告详情。
 *
 * `run` 是对应的执行记录摘要，`tool_calls` 是该轮的工具调用留痕。
 */
export interface ReportDetail {
  id: Id;
  run_id: Id;
  format: string;
  file_size: number;
  generated_at: string;
  run: AgentRunBrief;
  tool_calls: AgentToolCallDetail[];
}
