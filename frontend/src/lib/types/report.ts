import type { Id, PaginatedResponse } from "./common";
import type { AgentRunBrief, AgentToolCallDetail } from "./agent-run";

export interface Report {
  id: Id;
  run_id: Id;
  format: string;
  file_size: number;
  generated_at: string;
  /** 所属执行记录的标题（后端 join 出来，不是报告自己的字段） */
  run_title: string;
}

export type ReportListResponse = PaginatedResponse<Report>;

/**
 * 报告详情。
 *
 * 改造前这里是 `test_run` + `test_results`；现在挂的是执行记录本身
 * （`run`）和工具调用留痕（`tool_calls`）——报告的语义从「测试用例跑了
 * 什么结果」变成了「这轮 ReAct 调了哪些工具、返回了什么」。
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
