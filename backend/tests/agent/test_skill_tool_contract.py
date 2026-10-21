"""内置技能与工具集的**一致性契约**。

这类 bug 极隐蔽：SKILL.md 里把 ``allowed_tools`` 写错一个字符，运行时不报错，
只是那个工具被静默裁掉——模型看不到它，行为退化成「技能好像没起作用」。
所以用一条测试把「技能声明的工具必须真实存在」钉死。
"""

from __future__ import annotations

import pytest

from src.agent.modes import SIDE_EFFECT_TOOL_NAMES
from src.agent.tools.registry import build_tools
from src.skill.repository import SkillRepository


@pytest.fixture(scope="module")
def builtin_skills():
    # space_id=None 只扫内置目录
    return SkillRepository().discover(None)


@pytest.fixture(scope="module")
def all_tool_names() -> set[str]:
    return set(build_tools(space_id=1, mode="agent").names)


class TestSkillDeclarationContract:
    def test_builtin_skills_exist(self, builtin_skills):
        """内置技能是产品的一部分，缺了说明打包漏了文件。"""
        names = {skill.name for skill in builtin_skills}
        assert {"api-test-design", "api-regression-run"} <= names

    def test_declared_tools_all_exist(self, builtin_skills, all_tool_names):
        """声明的每个工具都必须能在工具集里找到。"""
        problems = []
        for skill in builtin_skills:
            missing = sorted(set(skill.manifest.allowed_tools) - all_tool_names)
            if missing:
                problems.append(f"{skill.name}: 未知工具 {missing}")

        assert not problems, "；".join(problems)

    def test_declared_tools_actually_survive_filtering(self, builtin_skills):
        """声明了却不在 agent 模式下可用的工具，等于白声明。

        agent 模式留全部工具，所以这里校验的是「声明 ∩ 全量」不漏项——
        若某个工具被模式永久禁用，应该从 SKILL.md 里删掉而不是留着。
        """
        for skill in builtin_skills:
            if not skill.manifest.allowed_tools:
                continue
            bundle = build_tools(space_id=1, mode="agent", skill_names=[skill.name])
            assert set(bundle.names) == set(skill.manifest.allowed_tools), skill.name

    def test_ask_mode_narrows_skills_without_privilege_escalation(self, builtin_skills, all_tool_names):
        """skill 只能收窄，不能放大：ask 模式下有写工具声明的 skill 也不能带回写工具。"""
        for skill in builtin_skills:
            if not skill.manifest.allowed_tools:
                continue
            bundle = build_tools(space_id=1, mode="ask", skill_names=[skill.name])
            leaked = set(bundle.names) & SIDE_EFFECT_TOOL_NAMES
            assert not leaked, f"{skill.name} 在 ask 模式下泄漏了副作用工具 {leaked}"

    def test_plan_mode_has_no_send_request(self, builtin_skills):
        """plan 模式的核心承诺：不发请求。回归 skill 声明了 send_request 也不该生效。"""
        for skill in builtin_skills:
            bundle = build_tools(space_id=1, mode="plan", skill_names=[skill.name])
            assert "send_request" not in bundle.names, skill.name
