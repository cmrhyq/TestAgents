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
