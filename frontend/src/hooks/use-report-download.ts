/**
 * 把一份测试报告导出成独立 HTML 并触发下载。
 *
 * 纯前端实现：复用现有的三个 GET 接口拼数据，不新增后端。
 * 正文按需补拉，已展开过的条目直接命中 React Query 缓存，不重复发请求。
 */
import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { AgentToolCall, AgentToolCallDetail, ReportDetail } from "@/lib/types";
import { buildReportHtml, type ReportRequestEntry } from "@/lib/export/report-html";
import { buildTimestamp, downloadHtml, sanitizeFilename } from "@/lib/export/download";

/** 并发上限：一条 2MB 响应体同时拉 20 条会打满浏览器连接池，4 条是体感与稳定的折中。 */
const FETCH_CONCURRENCY = 4;

export interface DownloadProgress {
  loaded: number;
  total: number;
}

export interface UseReportDownloadResult {
  /** 触发一次导出；同一时刻只会有一份在生成 */
  download: (runId: string) => Promise<void>;
  isDownloading: boolean;
  /** 正文补拉进度；未在下载时为 null */
  progress: DownloadProgress | null;
}

/** 按固定并发跑一组异步任务，结果顺序与输入一致。 */
async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  worker: (item: T) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let cursor = 0;

  const runners = Array.from({ length: Math.min(limit, Math.max(items.length, 1)) }, async () => {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      results[index] = await worker(items[index]);
    }
  });

  await Promise.all(runners);
  return results;
}

export function useReportDownload(): UseReportDownloadResult {
  const queryClient = useQueryClient();
  const [isDownloading, setIsDownloading] = useState(false);
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  // state 更新是异步的，连点两次会同时进两次导出
  const busyRef = useRef(false);

  const download = useCallback(
    async (runId: string) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setIsDownloading(true);
      setProgress(null);

      try {
        // 列表页只有统计，没有请求清单：没有缓存就先取一次详情
        const detailKey = queryKeys.reports.detail(runId);
        const detail =
          queryClient.getQueryData<ReportDetail>(detailKey) ??
          (await queryClient.fetchQuery<ReportDetail>({
            queryKey: detailKey,
            queryFn: async () => (await api.get<ReportDetail>(`/reports/${runId}`)).data,
          }));

        const requests = detail.requests;
        let loaded = 0;
        setProgress({ loaded, total: requests.length });

        const entries = await mapWithConcurrency<AgentToolCall, ReportRequestEntry>(
          requests,
          FETCH_CONCURRENCY,
          async (call) => {
            const requestKey = queryKeys.reports.request(runId, call.id);
            const cached = queryClient.getQueryData<AgentToolCallDetail>(requestKey);

            let body: AgentToolCallDetail | null = cached ?? null;
            if (!body) {
              try {
                body = await queryClient.fetchQuery<AgentToolCallDetail>({
                  queryKey: requestKey,
                  queryFn: async () =>
                    (await api.get<AgentToolCallDetail>(`/reports/${runId}/requests/${call.id}`))
                      .data,
                  staleTime: 5 * 60 * 1000,
                });
              } catch {
                // 单条失败不能拖垮整份报告，正文缺失在文件里标注
                body = null;
              }
            }

            loaded += 1;
            setProgress({ loaded, total: requests.length });
            return { call, detail: body };
          }
        );

        const html = buildReportHtml({
          runId,
          detail,
          entries,
          exportedAt: new Date(),
        });

        const base = sanitizeFilename(
          `测试报告-RUN${runId}-${detail.run.title || "未命名"}-${buildTimestamp()}`,
          `测试报告-RUN${runId}`
        );
        downloadHtml(html, `${base}.html`);

        const missing = entries.filter((entry) => entry.detail === null).length;
        if (missing > 0) {
          toast.warning(`报告已下载，其中 ${missing} 条正文获取失败`, {
            description: "文件内已标注缺失条目，其余内容完整。",
          });
        } else {
          toast.success("报告已下载", {
            description: `共 ${entries.length} 条接口调用，文件名为 ${base}.html`,
          });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "未知错误";
        toast.error("报告导出失败", { description: message });
      } finally {
        busyRef.current = false;
        setIsDownloading(false);
        setProgress(null);
      }
    },
    [queryClient]
  );

  return { download, isDownloading, progress };
}
