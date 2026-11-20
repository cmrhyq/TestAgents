import { ListTodo, MessageSquare, Zap } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ConversationMode } from "@/lib/types";

interface ModeOption {
  value: ConversationMode;
  icon: React.ReactNode;
  label: string;
  hint: string;
}

/**
 * 三种对话模式的展示文案与提示。
 *
 * 文案须与后端工具白名单一致：`ask` 与 `plan` 模式下写工具不可用。
 */
const MODES: ModeOption[] = [
  {
    value: "agent",
    icon: <Zap className="h-3.5 w-3.5" />,
    label: "执行",
    hint: "自动选择工具：查接口、发请求、评估断言并落盘",
  },
  {
    value: "ask",
    icon: <MessageSquare className="h-3.5 w-3.5" />,
    label: "问答",
    hint: "只回答问题，可用工具全为只读，不会发任何请求",
  },
  {
    value: "plan",
    icon: <ListTodo className="h-3.5 w-3.5" />,
    label: "计划",
    hint: "只输出测试计划（接口范围 / 用例矩阵 / 断言策略 / 风险）",
  },
];

/** `ModeSelector` 的属性。 */
export interface ModeSelectorProps {
  value: ConversationMode;
  onChange(mode: ConversationMode): void;
  disabled?: boolean;
}

/** 对话模式分段控件。 */
export function ModeSelector({ value, onChange, disabled }: ModeSelectorProps) {
  return (
    <div
      role="radiogroup"
      aria-label="工作模式"
      className="inline-flex items-center gap-0.5 rounded-md bg-muted p-0.5"
    >
      {MODES.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={option.hint}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={cn(
              "flex h-6 items-center gap-1.5 rounded px-2 text-[12px] font-medium leading-4 transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
              active
                ? "bg-card text-foreground shadow-xs"
                : "text-muted-foreground hover:text-foreground",
              disabled && "cursor-not-allowed opacity-40"
            )}
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export { MODES as CHAT_MODES };
