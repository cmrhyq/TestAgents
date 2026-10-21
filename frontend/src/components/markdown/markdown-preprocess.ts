/** 全角标点 → 半角，避免 ** / ## 无法解析 */
function normalizeTypography(content: string): string {
  return content.replace(/\uFF0A/g, "*").replace(/\uFF03/g, "#");
}

function isFenceLine(line: string): boolean {
  return /^(`{3,}|~{3,})(\s*[\w-]*)?\s*$/.test(line.trim());
}

/** GFM 表格行（含分隔行 |---|） */
function isMarkdownTableLine(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed.includes("|")) {
    return false;
  }
  if (/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(trimmed)) {
    return true;
  }
  const pipeCount = (trimmed.match(/\|/g) ?? []).length;
  return pipeCount >= 2 && trimmed.startsWith("|");
}

function isMarkdownTableBlock(lines: string[], start: number): boolean {
  if (start >= lines.length || !isMarkdownTableLine(lines[start])) {
    return false;
  }
  if (start + 1 >= lines.length) {
    return false;
  }
  const separator = lines[start + 1].trim();
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(separator);
}

/** 检测是否像 ASCII 框线图/流程图（排除 Markdown 表格与纯分隔线） */
function isAsciiArtLine(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed || isFenceLine(trimmed) || isMarkdownTableLine(trimmed)) {
    return false;
  }
  if (/^-{3,}$/.test(trimmed)) {
    return false;
  }

  if (/[-─=]{2,}>/.test(trimmed)) {
    return true;
  }

  const diagramChars = trimmed.match(/[+─│┌┐└┘├┤┬┴┼→←↑↓═\\/>]/g);
  if (diagramChars && diagramChars.length >= 2) {
    return true;
  }

  if (/\+[-─+|+]+\+/.test(trimmed)) {
    return true;
  }

  return false;
}

function containsSubstantialMarkdown(text: string): boolean {
  return (
    /^#{1,6}\s/m.test(text) ||
    /\*\*[^*\n]+\*\*/.test(text) ||
    /^\|.+\|/m.test(text) ||
    /^\d+\.\s+\S/m.test(text) ||
    /^-\s+\S/m.test(text)
  );
}

/**
 * LLM 有时用 ```text 包裹整段回复，导致内部 Markdown 全部变成纯文本。
 * 若围栏内主要是 Markdown 而非 ASCII 图，则去掉外层围栏。
 */
function unwrapErroneousTextFences(content: string): string {
  const trimmed = content.trim();
  const wrapped = trimmed.match(/^(`{3,}|~{3,})\s*(?:text|txt)?\s*\n([\s\S]*?)\n\1\s*$/);
  if (wrapped) {
    const inner = wrapped[2];
    if (containsSubstantialMarkdown(inner) && !isMostlyAsciiArt(inner)) {
      return inner;
    }
  }

  const lines = content.split("\n");
  if (lines.length === 0 || !/^(`{3,}|~{3,})\s*(?:text|txt)?\s*$/.test(lines[0].trim())) {
    return content;
  }

  let closeIndex = -1;
  for (let i = 1; i < lines.length; i += 1) {
    if (isFenceLine(lines[i])) {
      closeIndex = i;
      break;
    }
  }

  const inner = closeIndex > 0 ? lines.slice(1, closeIndex).join("\n") : lines.slice(1).join("\n");
  const tail = closeIndex > 0 ? lines.slice(closeIndex + 1).join("\n") : "";

  if (containsSubstantialMarkdown(inner) && !isMostlyAsciiArt(inner)) {
    return tail ? `${inner}\n${tail}` : inner;
  }

  return content;
}

function isMostlyAsciiArt(text: string): boolean {
  const lines = text.split("\n").filter((line) => line.trim());
  if (lines.length === 0) {
    return false;
  }
  const asciiCount = lines.filter((line) => isAsciiArtLine(line)).length;
  return asciiCount / lines.length > 0.5;
}

/** 流式期间若围栏未闭合，临时补全以便解析围栏外的 Markdown */
function closeOpenFenceForStreaming(content: string, isStreaming: boolean): string {
  if (!isStreaming) {
    return content;
  }
  const fenceCount = (content.match(/^(`{3,}|~{3,})/gm) ?? []).length;
  if (fenceCount % 2 === 1) {
    return `${content}\n\`\`\``;
  }
  return content;
}

function preprocessUnfencedSegment(content: string): string {
  if (!content) {
    return content;
  }

  const lines = content.split("\n");
  const result: string[] = [];
  let index = 0;

  while (index < lines.length) {
    if (isMarkdownTableBlock(lines, index)) {
      let end = index + 2;
      while (end < lines.length && isMarkdownTableLine(lines[end])) {
        end += 1;
      }
      result.push(...lines.slice(index, end));
      index = end;
      continue;
    }

    if (!isAsciiArtLine(lines[index])) {
      result.push(lines[index]);
      index += 1;
      continue;
    }

    const block: string[] = [];
    while (index < lines.length) {
      if (isMarkdownTableBlock(lines, index)) {
        break;
      }
      const line = lines[index];
      if (isAsciiArtLine(line)) {
        block.push(line);
        index += 1;
        continue;
      }
      if (line.trim() === "" && index + 1 < lines.length && isAsciiArtLine(lines[index + 1])) {
        block.push(line);
        index += 1;
        continue;
      }
      break;
    }

    const cleaned = block.filter((line) => !isFenceLine(line));
    if (cleaned.length >= 2) {
      result.push("```text", ...cleaned, "```");
    } else {
      result.push(...block);
    }
  }

  return result.join("\n");
}

/** 按围栏分段，仅对非围栏区域做 ASCII 图补全；已有围栏块原样保留 */
function preprocessWithFenceAwareness(content: string): string {
  const lines = content.split("\n");
  const output: string[] = [];
  let unfencedBuffer: string[] = [];
  let inFence = false;
  let fencedBuffer: string[] = [];

  const flushUnfenced = () => {
    if (unfencedBuffer.length > 0) {
      output.push(preprocessUnfencedSegment(unfencedBuffer.join("\n")));
      unfencedBuffer = [];
    }
  };

  for (const line of lines) {
    if (isFenceLine(line)) {
      if (!inFence) {
        flushUnfenced();
        inFence = true;
        fencedBuffer = [line];
      } else {
        fencedBuffer.push(line);
        output.push(fencedBuffer.join("\n"));
        fencedBuffer = [];
        inFence = false;
      }
      continue;
    }

    if (inFence) {
      fencedBuffer.push(line);
    } else {
      unfencedBuffer.push(line);
    }
  }

  if (inFence) {
    output.push(fencedBuffer.join("\n"));
  }
  flushUnfenced();

  return output.join("\n");
}

/** Markdown 渲染前统一预处理 */
export function preprocessMarkdown(content: string, isStreaming = false): string {
  if (!content) {
    return content;
  }

  let result = normalizeTypography(content);
  result = unwrapErroneousTextFences(result);
  result = closeOpenFenceForStreaming(result, isStreaming);
  result = preprocessWithFenceAwareness(result);
  return result;
}
