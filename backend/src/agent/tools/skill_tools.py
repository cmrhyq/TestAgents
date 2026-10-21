"""技能工具：list_skills / read_skill。

为什么还需要这两个工具？用户可能只选了 skill A，但对话中途需要参考 skill B 的
方法论。这时让 Agent 自己「翻阅技能库」比让用户回去勾选再发一次更顺手。
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from src.core.logging import get_logger
from src.skill.service import SkillService

logger = get_logger(__name__)


def make_skill_tools(space_id: int | str, service: SkillService | None = None) -> list[BaseTool]:
    """构造技能查询工具。"""
    skills = service or _default_service()

    @tool
    def list_skills() -> str:
        """列出当前可用的测试技能（内置 + 本空间导入的）。

        当用户问「你有哪些能力」「有没有针对 XX 场景的方法」时使用。
        """
        try:
            discovered = skills.list_skills(space_id)
        except Exception as exc:
            logger.error("技能列表读取失败", error=str(exc))
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

        return json.dumps(
            [
                {
                    "name": skill.name,
                    "description": skill.manifest.description,
                    "when_to_use": skill.manifest.when_to_use,
                    "scope": skill.scope,
                }
                for skill in discovered
            ],
            ensure_ascii=False,
        )

    @tool
    def read_skill(name: str) -> str:
        """读取某个技能的完整方法论正文。

        当用户提到某个技能，或你判断需要按某套既有方法论来做（如"按接口测试设计规范"）时使用。

        Args:
            name: 技能名，可从 list_skills 的结果里取
        """
        skill = skills.find(name, space_id)
        if skill is None:
            return json.dumps({"error": f"技能不存在: {name}，可先用 list_skills 查看"}, ensure_ascii=False)
        return skill.manifest.to_prompt_block()

    return [list_skills, read_skill]


def _default_service() -> SkillService:
    from src.skill.service import get_skill_service

    return get_skill_service()
