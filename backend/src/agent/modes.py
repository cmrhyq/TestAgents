"""工作模式策略：默认 / 问答 / 计划。

模式以工具白名单实现，而非仅靠提示词约束：被禁用的工具不进入模型工具列表，
skill 声明的 ``allowed_tools`` 只能在当前模式的基础上进一步收窄。
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import BaseTool

from agent.prompt.agent import AGENT_MODE_INSTRUCTIONS
from data.enum.agent import Mode

# 默认模式的最大工具调用轮次。兜住模型陷入死循环的情况。
DEFAULT_MAX_STEPS = 100
# 计划模式只需要读信息 + 输出计划，轮次更少
PLAN_MAX_STEPS = 80

# 有副作用的工具：改动外部状态或持久化数据
SIDE_EFFECT_TOOL_NAMES = frozenset(
    {
        "send_request",
        "write_file",
        "delete_file",
        "remember",
        "forget",
    }
)

# 只读工具：ask / plan 模式可用的全部工具
READ_ONLY_TOOL_NAMES = frozenset(
    {
        "search_space",
        "get_space_endpoints",
        "get_endpoint_detail_by_id",
        "read_file",
        "list_directory",
        "list_environments",
        "recall",
        "knowledge_search",
        "list_skills",
        "read_skill",
        "evaluate_assertions",
        "extract_jsonpath",
    }
)

_MODE_ALIASES = {
    "agent": Mode.AGENT,
    "ask": Mode.ASK,
    "plan": Mode.PLAN,
}

_MODE_LABELS = {Mode.AGENT: "执行", Mode.ASK: "问答", Mode.PLAN: "计划"}


@dataclass(frozen=True, slots=True)
class ModePolicy:
    """某个模式下的执行策略。"""

    mode: Mode
    allow_side_effects: bool
    instruction: str
    max_steps: int

    @property
    def label(self) -> str:
        """模式的中文显示名。"""
        return _MODE_LABELS[self.mode]

    @property
    def blocked_tool_names(self) -> frozenset[str]:
        """当前模式下禁用的工具名；允许副作用时为空集合。"""
        return frozenset() if self.allow_side_effects else SIDE_EFFECT_TOOL_NAMES


def normalize_mode(raw: str | None) -> Mode:
    """把外部传入的 mode 归一化为 ``Mode``。

    Args:
        raw: 原始模式字符串，可为 None

    Returns:
        归一化后的模式
    """
    key = (raw or "").strip().lower()
    return _MODE_ALIASES.get(key, Mode.AGENT)


def policy_for(raw: str | Mode | None) -> ModePolicy:
    """按模式构造执行策略。

    Args:
        raw: 模式字符串或 ``Mode``；None 视为默认模式

    Returns:
        该模式的执行策略
    """
    mode = raw if isinstance(raw, Mode) else normalize_mode(raw)
    return ModePolicy(
        mode=mode,
        allow_side_effects=mode is Mode.AGENT,
        instruction=AGENT_MODE_INSTRUCTIONS[mode],
        max_steps=PLAN_MAX_STEPS if mode is Mode.PLAN else DEFAULT_MAX_STEPS,
    )


def filter_tools(
    tools: list[BaseTool],
    policy: ModePolicy,
    skill_allowed: set[str] | None = None,
) -> list[BaseTool]:
    """按模式与 skill 声明裁剪工具列表。

    先移除当前模式禁用的副作用工具，再按 skill 声明的 ``allowed_tools`` 过滤，
    因此 skill 只能收窄范围，无法放开模式已禁用的工具。

    Args:
        tools: 全量候选工具
        policy: 模式策略
        skill_allowed: 选中 skill 声明的工具名并集；None 表示不额外限制

    Returns:
        裁剪后的工具列表，保持原顺序
    """
    blocked = policy.blocked_tool_names
    result = [tool for tool in tools if tool.name not in blocked]

    if skill_allowed is not None:
        result = [tool for tool in result if tool.name in skill_allowed]

    return result
