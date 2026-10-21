/** 流式输出末尾光标：1px 精致闪烁竖线（step 动画，不抢眼）。 */
export function StreamingCursor() {
  return (
    <span
      className="markdown-streaming-cursor ml-0.5 inline-block h-[1em] w-px translate-y-0.5 bg-primary align-middle animate-cursor-blink"
      aria-hidden="true"
    />
  );
}
