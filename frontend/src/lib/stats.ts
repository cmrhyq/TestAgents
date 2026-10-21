/** 响应耗时统计。 */

export interface ResponseStats {
  avg: number;
  min: number;
  max: number;
  p95: number;
}

/** 计算 avg/min/max/p95（毫秒）；无有效数据时返回 null。 */
export function computeResponseStats(times: number[]): ResponseStats | null {
  const valid = times.filter((t) => t > 0);
  if (valid.length === 0) return null;

  const sorted = [...valid].sort((a, b) => a - b);
  const p95Idx = Math.min(Math.floor(sorted.length * 0.95), sorted.length - 1);

  return {
    avg: valid.reduce((a, b) => a + b, 0) / valid.length,
    min: sorted[0],
    max: sorted[sorted.length - 1],
    p95: sorted[p95Idx],
  };
}
