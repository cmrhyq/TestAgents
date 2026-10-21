import { createCrudHooks } from "@/lib/create-crud-hooks";
import { queryKeys } from "@/lib/query-keys";
import type { Environment, EnvironmentListResponse } from "@/lib/types";

interface UseEnvironmentsParams {
  space_id?: string | number;
  keyword?: string;
  page?: number;
  page_size?: number;
}

const {
  useList: useEnvironments,
  useCreate: useCreateEnvironment,
  useUpdate: useUpdateEnvironment,
  useDelete: useDeleteEnvironment,
} = createCrudHooks<Environment, EnvironmentListResponse, UseEnvironmentsParams>({
  queryKeys: queryKeys.environments,
  basePath: "/environments",
  labels: {
    createSuccess: "环境创建成功",
    createError: "环境创建失败",
    updateSuccess: "环境更新成功",
    updateError: "环境更新失败",
    deleteSuccess: "环境删除成功",
    deleteError: "环境删除失败",
  },
});

export { useEnvironments, useCreateEnvironment, useUpdateEnvironment, useDeleteEnvironment };
