"""工具装配。

一次对话的工具集合由模式、选中的 skill 与会话上下文决定；``runner`` 只负责跑循环。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.tools import BaseTool

from src.agent.modes import ModePolicy, filter_tools, policy_for
from src.agent.tools.db_tools import make_db_tools, search_space
from src.agent.tools.executor_tools import make_executor_tools
from src.agent.tools.fs_tools import make_fs_tools
from src.agent.tools.http_tools import make_http_tools
from src.agent.tools.knowledge_tools import make_knowledge_tools
from src.agent.tools.memory_tools import make_memory_tools
from src.agent.tools.skill_tools import make_skill_tools
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ToolBundle:
    """一次对话的工具集合与策略。"""

    tools: list[BaseTool]
    policy: ModePolicy
    skill_allowed: set[str] | None = None
    suppressed: list[str] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        """工具名列表，保持装配顺序。"""
        return [tool.name for tool in self.tools]


def build_tools(
    space_id: int | str,
    mode: str | None = "agent",
    skill_names: list[str] | None = None,
    conversation_id: int | None = None,
    environment_id: int | None = None,
) -> ToolBundle:
    """按模式与 skill 装配本轮工具。

    Args:
        space_id: 空间 ID（所有空间相关工具都绑定它）
        mode: 工作模式（agent / ask / plan，容忍旧值）
        skill_names: 选中的 skill 名
        conversation_id: 会话 ID（记忆归属用）
        environment_id: 指定测试环境

    Returns:
        ``ToolBundle``，含已过滤的工具、策略与被裁掉的工具名
    """
    policy = policy_for(mode)
    selected = skill_names or []

    candidates: list[BaseTool] = [search_space]
    candidates += make_db_tools(space_id)
    candidates += make_fs_tools(space_id)
    candidates += make_http_tools(space_id, environment_id)
    candidates += make_executor_tools()
    candidates += make_memory_tools(space_id, conversation_id)
    candidates += make_knowledge_tools(space_id)
    candidates += make_skill_tools(space_id)

    skill_allowed = _skill_allowed_tools(selected, space_id)
    tools = filter_tools(candidates, policy, skill_allowed)

    suppressed = sorted({tool.name for tool in candidates} - {tool.name for tool in tools})
    if suppressed:
        logger.debug("工具已按模式/技能裁剪", mode=policy.mode.value, suppressed=suppressed)

    return ToolBundle(tools=tools, policy=policy, skill_allowed=skill_allowed, suppressed=suppressed)


def _skill_allowed_tools(skill_names: list[str], space_id: int | str) -> set[str] | None:
    """取 skill 声明的工具并集；读取失败时不做额外限制。"""
    if not skill_names:
        return None
    try:
        from src.skill.service import get_skill_service

        return get_skill_service().resolve_allowed_tools(skill_names, space_id)
    except Exception as exc:
        logger.warning("skill 工具声明读取失败，忽略技能限制", error=str(exc))
        return None
