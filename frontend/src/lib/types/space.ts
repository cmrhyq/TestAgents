import type { Id, PaginatedResponse } from "./common";

export interface Space {
  id: Id;
  name: string;
  description: string;
  status: number;
  created_at: string;
  updated_at: string;
}

export type SpaceListResponse = PaginatedResponse<Space>;

/** OpenAPI 解析结果（POST /spaces/parse/openapi/{space_id}）。 */
export interface ParseOpenAPIResponse {
  run_id: Id | null;
  status: string;
  message: string;
  endpoints_count: number;
}

/** OpenAPI 文件上传结果。 */
export interface UploadOpenAPIResponse {
  filename: string;
  path: string;
  status: string;
  message: string;
}
