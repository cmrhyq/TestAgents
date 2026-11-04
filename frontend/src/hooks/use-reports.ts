import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { AgentToolCallDetail, ReportListResponse, ReportDetail } from "@/lib/types";

interface UseReportsParams {
  space_id?: string | number;
  status?: string;
  page?: number;
  page_size?: number;
}

/** 报告列表：一行一个 run，只含发过 send_request 的执行。 */
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

/** 报告详情：执行摘要 + 统计 + 请求清单（不含正文）。 */
export function useReportDetail(runId: string | number) {
  return useQuery<ReportDetail>({
    queryKey: queryKeys.reports.detail(runId),
    queryFn: async () => {
      const { data } = await api.get<ReportDetail>(`/reports/${runId}`);
      return data;
    },
    enabled: !!runId,
  });
}

/**
 * 单条请求的完整请求/响应正文（懒加载）。
 *
 * `enabled` 由「是否展开」控制：不展开就不发请求。
 * 结果按 `(runId, requestId)` 缓存，收起再展开不会重复拉。
 */
export function useReportRequest(
  runId: string | number,
  requestId: string | number,
  enabled: boolean
) {
  return useQuery<AgentToolCallDetail>({
    queryKey: queryKeys.reports.request(runId, requestId),
    queryFn: async () => {
      const { data } = await api.get<AgentToolCallDetail>(
        `/reports/${runId}/requests/${requestId}`
      );
      return data;
    },
    enabled: !!runId && !!requestId && enabled,
    staleTime: 5 * 60 * 1000,
  });
}
