import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { StatusBadge } from "@/components/shared/status-badge.tsx";
import { HttpMethodBadge } from "@/components/shared/http-method-badge.tsx";
import type { TestResultDetail } from "@/lib/types.ts";
import { formatResponseTime } from "@/lib/format";
import { cn } from "@/lib/utils.ts";
import { HttpPayloadPanel } from "./http-payload-panel";

function ExpandableRow({ result }: { result: TestResultDetail }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className="border-b border-border transition-colors hover:bg-card cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-3">
          <span className="inline-flex items-center text-muted-foreground">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        </td>
        <td className="px-4 py-3 font-medium">{result.case_name}</td>
        <td className="px-4 py-3">
          <HttpMethodBadge method={result.request_method} />
        </td>
        <td className="px-4 py-3">
          <StatusBadge status={result.status} />
        </td>
        <td className="px-4 py-3">
          <span className="tabular-nums">{result.response_status_code ?? "—"}</span>
        </td>
        <td className="px-4 py-3">
          <span className="tabular-nums">{formatResponseTime(result.response_time)}</span>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border-subtle bg-muted/30">
          <td colSpan={6} className="px-4 py-4">
            <HttpPayloadPanel result={result} />
          </td>
        </tr>
      )}
    </>
  );
}

/** 测试结果表格（danger=true 时表头使用失败样式）。 */
export function TestResultsTable({ results, danger = false }: { results: TestResultDetail[]; danger?: boolean }) {
  return (
    <div className="w-full overflow-hidden rounded-lg border-0 shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className={cn("border-b border-border/30", danger ? "bg-destructive/5" : "bg-card")}>
            <tr>
              <th className="w-10 px-4 py-3" />
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">用例名称</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">方法</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">状态</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">状态码</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">耗时</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <ExpandableRow key={String(r.id)} result={r} />
            ))}
            {results.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-muted-foreground">
                  暂无测试结果
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
