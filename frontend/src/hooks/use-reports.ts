import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { ReportListResponse, ReportDetail } from "@/lib/types";

interface UseReportsParams {
  run_id?: string | number;
  page?: number;
  page_size?: number;
}

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

export function downloadReport(id: string | number) {
  const url = `/api/v1/reports/${id}/download`;
  window.open(url, "_blank");
}
