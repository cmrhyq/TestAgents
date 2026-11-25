import type { Id, PaginatedResponse } from "./common";

/** 接口定义，字段对应 OpenAPI 解析结果落库后的列。 */
export interface Endpoint {
  id: Id;
  space_id: Id;
  operation_id: string;
  name: string;
  path: string;
  method: string;
  /** 标签数组。服务端库内存的是 JSON 字符串，接口层已解析为数组。 */
  tags: string[];
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

/** 接口列表的分页响应。 */
export type EndpointListResponse = PaginatedResponse<Endpoint>;

/** 空间内的标签聚合项：标签名与带该标签的接口数量。 */
export interface EndpointTagFacet {
  name: string;
  count: number;
}
