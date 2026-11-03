import { useEffect, useState } from "react";

/**
 * 值节流：`value` 变化后延迟 `delayMs` 毫秒更新返回值。
 *
 * `delayMs <= 0` 时直接返回原值。
 */
export function useThrottledValue<T>(value: T, delayMs: number): T {
  const [throttled, setThrottled] = useState(value);

  useEffect(() => {
    if (delayMs <= 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      setThrottled(value);
    }, delayMs);

    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  if (delayMs <= 0) {
    return value;
  }

  return throttled;
}
