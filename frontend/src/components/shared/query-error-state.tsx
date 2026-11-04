import type { ReactNode } from "react";

/** 查询失败时的统一提示与恢复动作。 */
export function QueryErrorState({ message = "加载失败，请稍后重试", action }: { message?: string; action?: ReactNode }) {
  return (
    <div className="flex h-48 flex-col items-center justify-center gap-3">
      <p className="text-sm text-destructive">{message}</p>
      {action}
    </div>
  );
}
