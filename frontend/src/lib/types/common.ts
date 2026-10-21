/** 通用类型。 */

export type Id = string | number;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
