import { useEffect, useState } from "react";

/**
 * 防抖 hook：值变化后延迟 delayMs 毫秒才更新返回值。
 * 用于搜索输入等场景，避免每次按键都触发请求。
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    if (delayMs <= 0) return;
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return delayMs <= 0 ? value : debounced;
}
