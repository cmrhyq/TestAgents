import type { Id, PaginatedResponse } from "./common";
import type { TestRun } from "./test-run";

export interface Report {
  id: Id;
  run_id: Id;
  format: string;
  file_size: number;
  generated_at: string;
  test_run_name: string;
}

export type ReportListResponse = PaginatedResponse<Report>;

export interface TestResultDetail {
  id: Id;
  case_id: string;
  case_name: string;
  status: string;
  request_url: string;
  request_method: string;
  request_headers: string;
  request_body: string | null;
  query_params: string | null;
  response_status_code: number | null;
  response_headers: string;
  response_body: string | null;
  response_time: number;
  error_message: string;
  retry_count: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface ReportDetail {
  id: Id;
  run_id: Id;
  format: string;
  file_size: number;
  generated_at: string;
  test_run: TestRun;
  test_results: TestResultDetail[];
}
