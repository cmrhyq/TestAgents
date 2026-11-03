"""技能声明与工具集的一致性契约。

`SKILL.md` 的 `allowed_tools` 写错不会在运行时报错，只会静默裁掉工具，
故用测试固化「声明的工具必须真实存在且不被模式过滤掉」。
"""

from __future__ import annotations

import pytest

from src.agent.modes import SIDE_EFFECT_TOOL_NAMES
from src.agent.tools.registry import build_tools
from src.skill.repository import SkillRepository


@pytest.fixture(scope="module")
def builtin_skills():
    # space_id=None 时只扫描内置技能目录
    return SkillRepository().discover(None)


@pytest.fixture(scope="module")
def all_tool_names() -> set[str]:
    return set(build_tools(space_id=1, mode="agent").names)


class TestSkillDeclarationContract:
    """技能声明的工具必须存在，且模式过滤只收窄不放宽。"""

    def test_builtin_skills_exist(self, builtin_skills):
        """内置技能随包分发，缺失即打包遗漏。"""
        names = {skill.name for skill in builtin_skills}
        assert {"api-test-design", "api-regression-run"} <= names

    def test_declared_tools_all_exist(self, builtin_skills, all_tool_names):
        """声明的每个工具都必须在全量工具集中存在。"""
        problems = []
        for skill in builtin_skills:
            missing = sorted(set(skill.manifest.allowed_tools) - all_tool_names)
            if missing:
                problems.append(f"{skill.name}: 未知工具 {missing}")

        assert not problems, "；".join(problems)

    def test_declared_tools_actually_survive_filtering(self, builtin_skills):
        """声明且可用的工具应完整出现在 agent 模式工具集中。

        若某工具被模式永久禁用，应从 `SKILL.md` 删除声明而非保留。
        """
        for skill in builtin_skills:
            if not skill.manifest.allowed_tools:
                continue
            bundle = build_tools(space_id=1, mode="agent", skill_names=[skill.name])
            assert set(bundle.names) == set(skill.manifest.allowed_tools), skill.name

    def test_ask_mode_narrows_skills_without_privilege_escalation(self, builtin_skills, all_tool_names):
        """ask 模式下技能只能收窄工具集，不得带回副作用工具。"""
        for skill in builtin_skills:
            if not skill.manifest.allowed_tools:
                continue
            bundle = build_tools(space_id=1, mode="ask", skill_names=[skill.name])
            leaked = set(bundle.names) & SIDE_EFFECT_TOOL_NAMES
            assert not leaked, f"{skill.name} 在 ask 模式下泄漏了副作用工具 {leaked}"

    def test_plan_mode_has_no_send_request(self, builtin_skills):
        """plan 模式不发出外部请求，技能声明 `send_request` 也不得生效。"""
        for skill in builtin_skills:
            bundle = build_tools(space_id=1, mode="plan", skill_names=[skill.name])
            assert "send_request" not in bundle.names, skill.name
