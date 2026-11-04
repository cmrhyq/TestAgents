"""技能工具：``list_skills`` / ``read_skill``。

支持在对话中途查阅未选中的 skill，无需用户重新勾选后再发一次。
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from src.core.logging import get_logger
from src.skill.service import SkillService

logger = get_logger(__name__)


def make_skill_tools(space_id: int | str, service: SkillService | None = None) -> list[BaseTool]:
    """构造技能查询工具。

    Args:
        space_id: 空间 ID，决定可发现的技能范围
        service: 技能服务实例；None 时使用全局实例

    Returns:
        工具列表：``list_skills``、``read_skill``
    """
    skills = service or _default_service()

    @tool
    def list_skills() -> str:
        """列出当前可用的测试技能（内置 + 本空间导入的）。

        用于回答可用能力、以及是否存在某类场景的既有方法。
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

        用于按某套既有方法论执行（如「按接口测试设计规范」）。
        技能不存在时返回带 error 字段的 JSON 对象。

        Args:
            name: 技能名，可从 list_skills 的结果里取
        """
        skill = skills.find(name, space_id)
        if skill is None:
            return json.dumps({"error": f"技能不存在: {name}，可先用 list_skills 查看"}, ensure_ascii=False)
        return skill.manifest.to_prompt_block()

    return [list_skills, read_skill]


def _default_service() -> SkillService:
    """返回全局技能服务实例。"""
    from src.skill.service import get_skill_service

    return get_skill_service()
