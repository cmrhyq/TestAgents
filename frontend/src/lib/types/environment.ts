import type { Id, PaginatedResponse } from "./common";

/** 测试环境，含 `base_url` 与变量集。 */
export interface Environment {
  id: Id;
  space_id: Id;
  name: string;
  base_url: string;
  description: string;
  variables: string;
  is_default: number;
  status: number;
  created_at: string;
  updated_at: string;
}

/** 环境列表的分页响应。 */
export type EnvironmentListResponse = PaginatedResponse<Environment>;
