import { useEffect, useState } from "react";

/**
 * 对 value 做节流更新，delayMs <= 0 时立即返回原值。
 * 用于流式 Markdown 场景，降低每个 chunk 触发的重解析频率。
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
