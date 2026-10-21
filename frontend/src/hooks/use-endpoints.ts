import { createCrudHooks } from "@/lib/create-crud-hooks";
import { queryKeys } from "@/lib/query-keys";
import type { Endpoint, EndpointListResponse } from "@/lib/types";

interface UseEndpointsParams {
  space_id?: string | number;
  method?: string;
  keyword?: string;
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

export { useEndpoints, useEndpoint, useCreateEndpoint, useUpdateEndpoint, useDeleteEndpoint };
