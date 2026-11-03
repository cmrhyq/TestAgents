import { useEffect, useState } from "react";

/**
 * 值防抖：`value` 停止变化 `delayMs` 毫秒后才更新返回值。
 *
 * `delayMs <= 0` 时直接返回原值，不做延迟。
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
