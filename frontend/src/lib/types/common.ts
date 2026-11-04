/** 跨领域共用的基础类型。 */

/** 资源标识，字符串或数字。 */
export type Id = string | number;

/** 分页响应的通用包装。 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
