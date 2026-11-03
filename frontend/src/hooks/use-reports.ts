import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { ReportListResponse, ReportDetail } from "@/lib/types";

interface UseReportsParams {
  run_id?: string | number;
  page?: number;
  page_size?: number;
}

/** 报告列表，支持按执行记录与分页筛选。 */
export function useReports(params?: UseReportsParams) {
  return useQuery<ReportListResponse>({
    queryKey: queryKeys.reports.list(params),
    queryFn: async () => {
      const { data } = await api.get<ReportListResponse>("/reports/", {
        params,
      });
      return data;
    },
  });
}

/** 报告详情，含执行记录摘要与工具调用留痕。 */
export function useReportDetail(id: string | number) {
  return useQuery<ReportDetail>({
    queryKey: queryKeys.reports.detail(id),
    queryFn: async () => {
      const { data } = await api.get<ReportDetail>(`/reports/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

/** 在新标签页打开报告下载链接。 */
export function downloadReport(id: string | number) {
  const url = `/api/v1/reports/${id}/download`;
  window.open(url, "_blank");
}
