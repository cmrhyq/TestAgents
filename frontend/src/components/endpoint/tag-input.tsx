/**
 * 接口标签输入框。
 *
 * 交互约定：回车或逗号提交、退格在空输入时删除最后一个、失焦时自动提交未确认的
 * 草稿。上限与字符校验先在前端拦一次，服务端仍有兜底校验。
 */
import { useMemo, useState } from "react";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";
import { TAG_MAX_COUNT, normalizeTags, validateTag } from "@/lib/endpoint-tags";

interface TagInputProps {
  /** 输入框 id，同时用于派生错误提示的 id */
  id?: string;
  /** 当前标签数组 */
  value: string[];
  onChange(tags: string[]): void;
  /** 空间内已有标签，输入时做前缀/片段联想 */
  suggestions?: readonly string[];
  disabled?: boolean;
  /** 与外层表单字段的校验状态联动 */
  invalid?: boolean;
  placeholder?: string;
}

/** 标签输入：多值输入 + 联想 + 即时校验。 */
export function TagInput({
  id = "ep-tags",
  value,
  onChange,
  suggestions = [],
  disabled = false,
  invalid = false,
  placeholder = "输入后按回车添加，如：用户管理",
}: TagInputProps) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const errorId = `${id}-error`;

  const filtered = useMemo(() => {
    const keyword = draft.trim().toLowerCase();
    if (!keyword) return [];
    return suggestions
      .filter((item) => !value.some((tag) => tag.toLowerCase() === item.toLowerCase()))
      .filter((item) => item.toLowerCase().includes(keyword))
      .slice(0, 6);
  }, [draft, suggestions, value]);

  const commit = (raw: string) => {
    const message = validateTag(raw, value);
    if (message) {
      setError(message);
      return false;
    }
    const tag = raw.trim();
    if (!tag) return false;
    onChange(normalizeTags([...value, tag]));
    setDraft("");
    setError(null);
    return true;
  };

  const removeAt = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
    setError(null);
  };

  return (
    <div className="space-y-1.5">
      <div
        className={cn(
          "flex min-h-10 flex-wrap items-center gap-1.5 rounded-[2px] border border-border bg-input px-2 py-1.5 shadow-xs transition-shadow duration-200 ease-out-expo focus-within:border-primary/60 focus-within:shadow-input",
          (invalid || error) && "border-destructive"
        )}
      >
        {value.map((tag, index) => (
          <span
            key={`${tag}-${index}`}
            className="inline-flex items-center gap-1 rounded-[2px] border border-border bg-muted/40 px-1.5 py-0.5 font-mono text-[11px] leading-4 text-muted-foreground"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeAt(index)}
              disabled={disabled}
              aria-label={`移除标签 ${tag}`}
              className="text-muted-foreground/70 transition-colors hover:text-destructive disabled:opacity-50"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}

        <input
          id={id}
          value={draft}
          disabled={disabled || value.length >= TAG_MAX_COUNT}
          placeholder={value.length >= TAG_MAX_COUNT ? `已达上限 ${TAG_MAX_COUNT} 个` : placeholder}
          aria-invalid={invalid || !!error}
          aria-describedby={error || invalid ? errorId : undefined}
          onChange={(e) => {
            setDraft(e.target.value);
            if (error) setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === "," || e.key === "，") {
              e.preventDefault();
              commit(draft);
            } else if (e.key === "Backspace" && !draft && value.length > 0) {
              removeAt(value.length - 1);
            }
          }}
          onBlur={() => {
            if (draft.trim()) commit(draft);
          }}
          className="min-w-[120px] flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/60 disabled:cursor-not-allowed"
        />
      </div>

      {filtered.length > 0 && (
        <div className="flex flex-wrap gap-1">
          <span className="text-[11px] text-muted-foreground">已有：</span>
          {filtered.map((item) => (
            <button
              key={item}
              type="button"
              // 阻止默认行为以免先触发 input 的 blur，导致草稿被提前提交
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onChange(normalizeTags([...value, item]));
                setDraft("");
                setError(null);
              }}
              className="rounded-[2px] border border-dashed border-border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground transition-colors hover:border-accent/60 hover:text-accent"
            >
              {item}
            </button>
          ))}
        </div>
      )}

      {error && (
        <p id={errorId} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
