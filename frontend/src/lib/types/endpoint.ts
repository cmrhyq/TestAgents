import type { Id, PaginatedResponse } from "./common";

export interface Endpoint {
  id: Id;
  space_id: Id;
  operation_id: string;
  name: string;
  path: string;
  method: string;
  tags: string;
  summary: string;
  description: string;
  params: string;
  headers: string;
  body: string;
  responses: string;
  security: string;
  content_type: string;
  deprecated: number;
  status: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export type EndpointListResponse = PaginatedResponse<Endpoint>;
