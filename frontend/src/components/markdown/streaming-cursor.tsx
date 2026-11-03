/** 流式输出末尾的闪烁光标。 */
export function StreamingCursor() {
  return (
    <span
      className="markdown-streaming-cursor ml-0.5 inline-block h-[1em] w-px translate-y-0.5 bg-primary align-middle animate-cursor-blink"
      aria-hidden="true"
    />
  );
}
