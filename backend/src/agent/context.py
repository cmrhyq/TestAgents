"""System prompt 组装与裁剪。

拼装顺序：行为约束在前，内容注入在后。超过总长上限时按 skill → 记忆的顺序裁剪，
模式指令与工具规则不参与裁剪。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.agent.modes import ModePolicy
from src.agent.prompt.agent import AGENT_BASE_PERSONA, AGENT_TOOL_RULES
from src.data.constant.agent import AGENT_MAX_MEMORY_CHARS, AGENT_MAX_PROMPT_CHARS


@dataclass(slots=True)
class SpaceSnapshot:
    """空间快照：拼 prompt 需要的空间侧事实。"""

    space_id: int | str
    space_name: str
    endpoint_count: int = 0
    environments: list[dict[str, Any]] = field(default_factory=list)
    agents_md: str = ""


def build_system_prompt(
    space: SpaceSnapshot,
    policy: ModePolicy,
    memories: list[dict[str, Any]] | None = None,
    skill_blocks: str = "",
    max_chars: int = AGENT_MAX_PROMPT_CHARS,
) -> str:
    """组装本轮 system prompt。

    Args:
        space: 空间快照
        policy: 模式策略
        memories: 待注入的记忆条目（已按相关度/时间排好序）
        skill_blocks: 已渲染好的 skill 文本块
        max_chars: 总长上限

    Returns:
        完整 system prompt
    """
    # [1] 人设 + [2] 模式指令：永不裁剪
    head = f"{AGENT_BASE_PERSONA}\n\n## 当前工作模式\n\n{policy.instruction}"
    # [3] 空间上下文
    space_block = _render_space(space)
    # [6] 工具规则：永不裁剪
    rules = AGENT_TOOL_RULES

    fixed = "\n\n".join([head, space_block, rules])

    # [4] 记忆、[5] skill：按预算填充，超了先砍 skill
    memory_block = _render_memories(memories or [])
    budget = max_chars - len(fixed)

    if budget <= 0:
        # 极端情况：空间上下文过长，只能硬截
        return fixed[:max_chars] + "\n\n…（上下文过长，已截断）"

    memory_block = _fit(memory_block, min(len(memory_block), budget))
    budget -= len(memory_block)

    skill_blocks = _fit(skill_blocks, max(budget, 0))
    skill_blocks = _mark_truncated(skill_blocks, skill_blocks)

    parts = [head, space_block, memory_block, skill_blocks, rules]
    return "\n\n".join(part for part in parts if part)


def _render_space(space: SpaceSnapshot) -> str:
    lines = [
        "## 当前空间",
        "",
        f"- 空间名称：{space.space_name}",
        f"- 空间 ID：{space.space_id}",
        f"- 已登记接口数：{space.endpoint_count}",
    ]

    if space.environments:
        lines.append("- 测试环境：")
        for env in space.environments:
            flag = "（⚠️ 生产环境，请求会被拦截）" if env.get("is_production") else ""
            lines.append(f"  - {env.get('name', '?')}: {env.get('base_url', '')}{flag}")
    else:
        lines.append("- 测试环境：尚未配置（需要用户在「环境」里添加 base_url 后才能发请求）")

    if space.agents_md.strip():
        lines.extend(["", "## 空间约定（AGENTS.md）", "", space.agents_md.strip()])

    return "\n".join(lines)


def _render_memories(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return ""

    lines = ["## 相关记忆（跨会话）", "", "以下结论来自本空间此前的对话，可直接采用，不必重新确认：", ""]
    for item in memories:
        title = item.get("title", "")
        content = item.get("content", "")
        category = item.get("category", "fact")
        lines.append(f"- **[{category}] {title}**：{content}")

    block = "\n".join(lines)
    if len(block) > AGENT_MAX_MEMORY_CHARS:
        return block[:AGENT_MAX_MEMORY_CHARS] + "\n…（记忆过多，已截断）"
    return block


def _fit(text: str, budget: int) -> str:
    """把 text 压到 budget 以内；放不下就整体丢弃。"""
    if not text:
        return ""
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    if budget < 200:
        # 剩余预算太小，塞进去只会变成噪音，不如不给
        return ""
    return text[: budget - 40] + "\n…（内容过长，已截断）"


def _mark_truncated(original: str, fitted: str) -> str:
    """保留接口语义：调用方无需判断是否发生过截断。"""
    return fitted
