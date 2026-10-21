import { createCrudHooks } from "@/lib/create-crud-hooks";
import { queryKeys } from "@/lib/query-keys";
import type { Space, SpaceListResponse } from "@/lib/types";

interface UseSpacesParams {
  keyword?: string;
  status?: number;
  page?: number;
  page_size?: number;
}

const {
  useList: useSpaces,
  useDetail: useSpace,
  useCreate: useCreateSpace,
  useUpdate: useUpdateSpace,
  useDelete: useDeleteSpace,
} = createCrudHooks<Space, SpaceListResponse, UseSpacesParams>({
  queryKeys: queryKeys.spaces,
  basePath: "/spaces",
  labels: {
    createSuccess: "空间创建成功",
    createError: "空间创建失败",
    updateSuccess: "空间更新成功",
    updateError: "空间更新失败",
    deleteSuccess: "空间删除成功",
    deleteError: "空间删除失败",
  },
});

export { useSpaces, useSpace, useCreateSpace, useUpdateSpace, useDeleteSpace };
