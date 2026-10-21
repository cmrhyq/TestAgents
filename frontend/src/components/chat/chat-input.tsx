import { Loader2, Send } from "lucide-react";

import { ModeSelector } from "@/components/chat/mode-selector.tsx";
import { SkillSelector } from "@/components/chat/skill-selector.tsx";
import type { ConversationMode } from "@/lib/types";

export interface ChatInputProps {
  instruction: string;
  onInstructionChange(e: React.ChangeEvent<HTMLTextAreaElement>): void;
  onKeyDown(e: React.KeyboardEvent): void;
  mode: ConversationMode;
  onModeChange(mode: ConversationMode): void;
  spaceId: string | null;
  skillNames: string[];
  onToggleSkill(name: string): void;
  isStreaming: boolean;
  onSubmit(): void;
}

/**
 * 输入区：模式 + 技能 + 提示符输入 + 发送。
 *
 * 工具栏从左到右是「影响本轮行为的三个选择」→「动作」，
 * 顺序固定，用户不用每次找。
 */
export function ChatInput({
  instruction,
  onInstructionChange,
  onKeyDown,
  mode,
  onModeChange,
  spaceId,
  skillNames,
  onToggleSkill,
  isStreaming,
  onSubmit,
}: ChatInputProps) {
  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="rounded-[4px] border border-border bg-card px-3 py-2.5 shadow-xs transition-all duration-200 ease-out-expo focus-within:border-primary/50 focus-within:shadow-input">
        {/* 输入框：mono 提示符 + 多行输入 */}
        <div className="flex items-start gap-2">
          <span
            className="select-none pt-2 font-mono text-sm font-semibold text-primary"
            aria-hidden="true"
          >
            ❯
          </span>
          <textarea
            value={instruction}
            onChange={onInstructionChange}
            onKeyDown={onKeyDown}
            placeholder="今天帮你做些什么？例如：帮我为登录接口设计一组测试用例"
            rows={1}
            disabled={isStreaming}
            className="max-h-40 w-full resize-none bg-transparent px-0 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-60"
          />
        </div>

        {/* 工具栏 */}
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5">
            <ModeSelector value={mode} onChange={onModeChange} disabled={isStreaming} />
            <SkillSelector
              spaceId={spaceId}
              selected={skillNames}
              onToggle={onToggleSkill}
              disabled={isStreaming}
            />
          </div>

          <button
            type="button"
            onClick={onSubmit}
            disabled={!instruction.trim() || isStreaming}
            aria-label="发送"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors duration-200 ease-out-expo hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
