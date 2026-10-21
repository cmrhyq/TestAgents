import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import type { ResourceQueryKeys } from "@/lib/query-keys";

type ResourceId = string | number;

interface CrudLabels {
  createSuccess: string;
  createError: string;
  updateSuccess: string;
  updateError: string;
  deleteSuccess: string;
  deleteError: string;
}

interface CreateCrudHooksOptions {
  queryKeys: ResourceQueryKeys;
  basePath: string;
  labels: CrudLabels;
  toastOnCreate?: boolean;
}

export function createCrudHooks<
  TEntity,
  TList,
  TListParams = unknown,
  TCreate = Partial<TEntity>,
  TUpdate = Partial<TEntity>,
>(options: CreateCrudHooksOptions) {
  const { queryKeys, basePath, labels, toastOnCreate = true } = options;

  function useList(params?: TListParams) {
    return useQuery<TList>({
      queryKey: queryKeys.list(params),
      queryFn: async () => {
        const { data } = await api.get<TList>(`${basePath}/`, { params });
        return data;
      },
    });
  }

  function useDetail(id: ResourceId) {
    return useQuery<TEntity>({
      queryKey: queryKeys.detail(id),
      queryFn: async () => {
        const { data } = await api.get<TEntity>(`${basePath}/${id}`);
        return data;
      },
      enabled: Boolean(id),
    });
  }

  function useCreate() {
    const queryClient = useQueryClient();

    return useMutation<TEntity, Error, TCreate>({
      mutationFn: async (payload) => {
        const { data } = await api.post<TEntity>(`${basePath}/`, payload);
        return data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: queryKeys.all });
        if (toastOnCreate) {
          toast.success(labels.createSuccess);
        }
      },
      onError: (error) => {
        toast.error(error.message || labels.createError);
      },
    });
  }

  function useUpdate() {
    const queryClient = useQueryClient();

    return useMutation<TEntity, Error, { id: ResourceId; payload: TUpdate }>({
      mutationFn: async ({ id, payload }) => {
        const { data } = await api.put<TEntity>(`${basePath}/${id}`, payload);
        return data;
      },
      onSuccess: (_data, variables) => {
        queryClient.invalidateQueries({ queryKey: queryKeys.all });
        queryClient.invalidateQueries({ queryKey: queryKeys.detail(variables.id) });
        toast.success(labels.updateSuccess);
      },
      onError: (error) => {
        toast.error(error.message || labels.updateError);
      },
    });
  }

  function useDelete() {
    const queryClient = useQueryClient();

    return useMutation<void, Error, ResourceId>({
      mutationFn: async (id) => {
        await api.delete(`${basePath}/${id}`);
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: queryKeys.all });
        toast.success(labels.deleteSuccess);
      },
      onError: (error) => {
        toast.error(error.message || labels.deleteError);
      },
    });
  }

  return { useList, useDetail, useCreate, useUpdate, useDelete };
}
