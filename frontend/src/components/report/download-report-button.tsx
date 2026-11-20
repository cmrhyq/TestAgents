/** 报告下载按钮：列表行内用图标态，详情页页头用带文字的常态。 */
import type { MouseEvent, KeyboardEvent } from "react";
import { Download, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button.tsx";
import { useReportDownload } from "@/hooks/use-report-download.ts";
import { cn } from "@/lib/utils";

interface DownloadReportButtonProps {
  runId: string;
  /** 列表行内只显示图标，避免撑开列宽 */
  iconOnly?: boolean;
  className?: string;
}

export function DownloadReportButton({
  runId,
  iconOnly = false,
  className,
}: DownloadReportButtonProps) {
  const { download, isDownloading, progress } = useReportDownload();

  // 表格行整行可点击进入详情，行内按钮必须同时拦掉 click 与键盘事件
  const stop = (event: MouseEvent | KeyboardEvent) => event.stopPropagation();

  const label = isDownloading
    ? progress && progress.total > 0
      ? `导出中 ${progress.loaded}/${progress.total}`
      : "导出中"
    : "下载报告";

  return (
    <Button
      type="button"
      variant={iconOnly ? "ghost" : "outline"}
      size={iconOnly ? "icon-sm" : "sm"}
      className={cn(iconOnly && "text-muted-foreground", className)}
      disabled={isDownloading}
      aria-label={iconOnly ? label : undefined}
      title={iconOnly ? label : undefined}
      onClick={(event) => {
        stop(event);
        void download(runId);
      }}
      onKeyDown={(event) => {
        // 只拦冒泡：原生 button 的 Enter/Space 本来就会触发 click，这里再调一次会重复导出
        stop(event);
      }}
    >
      {isDownloading ? <Loader2 className="animate-spin" /> : <Download strokeWidth={1.75} />}
      {!iconOnly && <span>{label}</span>}
    </Button>
  );
}
