import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { Skill, SkillDetail, SkillListResponse } from "@/lib/types";

/**
 * 列出可见 skill（内置 + 空间私有）。空间级同名 skill 覆盖内置。
 *
 * ``spaceId`` 为空时只返回内置 skill——空间页之外的地方（如全局技能管理）
 * 用默认值即可，不需要挑空间。
 */
export function useSkills(spaceId?: string | number | null) {
  return useQuery<SkillListResponse>({
    queryKey: queryKeys.skills.list({ space_id: spaceId ?? null }),
    queryFn: async () => {
      const { data } = await api.get<SkillListResponse>("/skills", {
        params: spaceId ? { space_id: spaceId } : undefined,
      });
      return data;
    },
  });
}

/** 取单个 skill 详情（含 SKILL.md 正文）。 */
export function useSkill(name: string | null | undefined, spaceId?: string | number | null) {
  return useQuery<SkillDetail>({
    queryKey: queryKeys.skills.detail(`${name}:${spaceId ?? ""}`),
    queryFn: async () => {
      const { data } = await api.get<SkillDetail>(`/skills/${name}`, {
        params: spaceId ? { space_id: spaceId } : undefined,
      });
      return data;
    },
    enabled: Boolean(name),
  });
}

/** 启用 / 禁用 skill。禁用后不再出现在对话页的可选列表里。 */
export function useToggleSkill(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<Skill, Error, { name: string; enabled: boolean }>({
    mutationFn: async ({ name, enabled }) => {
      const { data } = await api.patch<Skill>(`/skills/${name}`, { enabled }, {
        params: spaceId ? { space_id: spaceId } : undefined,
      });
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skills.all });
      toast.success(variables.enabled ? "技能已启用" : "技能已禁用");
    },
    onError: (error) => {
      toast.error(error.message || "技能状态更新失败");
    },
  });
}

/** 导入 skill zip 包。 */
export function useImportSkill(spaceId?: string | number | null) {
  const queryClient = useQueryClient();

  return useMutation<SkillListResponse, Error, File>({
    mutationFn: async (file) => {
      const form = new FormData();
      form.append("file", file);

      // space_id 是 query 参数（决定装到哪个空间），不是表单字段
      const { data } = await api.post<SkillListResponse>("/skills/import", form, {
        params: spaceId ? { space_id: spaceId } : undefined,
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.skills.all });
      toast.success(`已导入 ${data.total} 个技能`);
    },
    onError: (error) => {
      toast.error(error.message || "技能导入失败");
    },
  });
}
