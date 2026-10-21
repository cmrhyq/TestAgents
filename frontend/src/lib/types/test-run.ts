import type { Id, PaginatedResponse } from "./common";

export interface TestRun {
  id: Id;
  space_id: Id | null;
  environment_id: Id | null;
  name: string;
  status: string;
  trigger_type: string;
  llm_provider: string;
  llm_model: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  skipped_cases: number;
  error_cases: number;
  pass_rate: number;
  started_at: string | null;
  finished_at: string | null;
  total_duration: number;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export type TestRunListResponse = PaginatedResponse<TestRun>;

export interface TestCaseBrief {
  id: Id;
  case_name: string;
  method: string;
  url: string;
  priority: string;
  status: string;
  created_at: string;
}

export interface TestResultBrief {
  id: Id;
  test_case_id: Id | null;
  status: string;
  status_code: number | null;
  response_time: number;
  assertion_passed: number;
  assertion_failed: number;
  error_message: string;
  created_at: string;
}

export interface TestRunDetail extends TestRun {
  test_cases: TestCaseBrief[];
  test_results: TestResultBrief[];
}

export interface ParseOpenAPIResponse {
  run_id: Id | null;
  status: string;
  message: string;
  endpoints_count: number;
}

export interface UploadOpenAPIResponse {
  filename: string;
  path: string;
  status: string;
  message: string;
}
