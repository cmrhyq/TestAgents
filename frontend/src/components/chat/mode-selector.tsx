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
 * 三种模式的说明文案要对齐**真实行为**，不是营销话术：
 * ask / plan 模式下模型手里根本没有写工具（后端工具白名单硬拦截），
 * 所以「不会执行」是可以承诺的，而不是「尽量不要执行」。
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

export interface ModeSelectorProps {
  value: ConversationMode;
  onChange(mode: ConversationMode): void;
  disabled?: boolean;
}

/** 模式分段控件：蓝图式标签页，选中态工程蓝底。 */
export function ModeSelector({ value, onChange, disabled }: ModeSelectorProps) {
  return (
    <div
      role="radiogroup"
      aria-label="工作模式"
      className="inline-flex items-center rounded-[3px] border border-border bg-background p-0.5"
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
              "flex items-center gap-1.5 rounded-[2px] px-2.5 py-1 text-xs font-medium transition-colors duration-150 ease-out-expo",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
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
