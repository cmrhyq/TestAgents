import type { Id, PaginatedResponse } from "./common";

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

export type EnvironmentListResponse = PaginatedResponse<Environment>;
