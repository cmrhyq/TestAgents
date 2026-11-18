import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import { createCrudHooks } from "@/lib/create-crud-hooks";
import { queryKeys } from "@/lib/query-keys";
import type { Endpoint, EndpointListResponse, EndpointTagFacet } from "@/lib/types";

interface UseEndpointsParams {
  space_id?: string | number;
  method?: string;
  keyword?: string;
  /** 标签筛选，多个用英文逗号分隔；空值表示不过滤。 */
  tags?: string;
  /** 多标签匹配方式：`any` 命中任一（默认），`all` 需全部命中。 */
  tags_mode?: "any" | "all";
  status?: number;
  page?: number;
  page_size?: number;
}

const {
  useList: useEndpoints,
  useDetail: useEndpoint,
  useCreate: useCreateEndpoint,
  useUpdate: useUpdateEndpoint,
  useDelete: useDeleteEndpoint,
} = createCrudHooks<Endpoint, EndpointListResponse, UseEndpointsParams>({
  queryKeys: queryKeys.endpoints,
  basePath: "/endpoints",
  labels: {
    createSuccess: "接口创建成功",
    createError: "接口创建失败",
    updateSuccess: "接口更新成功",
    updateError: "接口更新失败",
    deleteSuccess: "接口删除成功",
    deleteError: "接口删除失败",
  },
});

/**
 * 查询空间内的标签聚合（标签名 + 接口数）。
 *
 * 接口列表是分页的，前端无法从单页数据汇总出全量标签，所以单独取一次聚合结果，
 * 供筛选器候选项与表单标签联想使用。`spaceId` 为空时不发请求。
 */
export function useEndpointTags(spaceId: string | number | undefined) {
  return useQuery<EndpointTagFacet[]>({
    queryKey: queryKeys.endpoints.tags(spaceId),
    queryFn: async () => {
      const { data } = await api.get<EndpointTagFacet[]>("/endpoints/tags", {
        params: { space_id: spaceId },
      });
      return data;
    },
    enabled: Boolean(spaceId),
  });
}

/** 接口的增删改查 hook，由 `createCrudHooks` 按 `/endpoints` 生成。 */
export { useEndpoints, useEndpoint, useCreateEndpoint, useUpdateEndpoint, useDeleteEndpoint };
