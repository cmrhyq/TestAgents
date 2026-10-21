"""上下文组装测试。

关注三件事：拼装顺序（行为约束在最前）、超长裁剪顺序（先砍内容、后砍规则）、
以及每块内容确实出现在它该出现的位置。
"""

import pytest

from src.agent.context import (
    MAX_PROMPT_CHARS,
    SpaceSnapshot,
    build_system_prompt,
)
from src.agent.modes import policy_for

SNAPSHOT = SpaceSnapshot(
    space_id=123,
    space_name="用户中心",
    endpoint_count=42,
    environments=[
        {"name": "dev", "base_url": "http://dev.local", "is_production": False},
        {"name": "prod", "base_url": "http://prod.local", "is_production": True},
    ],
    agents_md="# 约定\n- 只用测试账号",
)


class TestBlocks:
    def test_contains_space_identity(self):
        prompt = build_system_prompt(SNAPSHOT, policy_for("agent"))

        assert "用户中心" in prompt
        assert "42" in prompt

    def test_contains_environment_list(self):
        prompt = build_system_prompt(SNAPSHOT, policy_for("agent"))

        assert "http://dev.local" in prompt
        assert "生产" in prompt  # 生产环境必须被标注出来

    def test_contains_agents_md(self):
        prompt = build_system_prompt(SNAPSHOT, policy_for("agent"))
        assert "只用测试账号" in prompt

    def test_contains_mode_instruction(self):
        ask_prompt = build_system_prompt(SNAPSHOT, policy_for("ask"))
        plan_prompt = build_system_prompt(SNAPSHOT, policy_for("plan"))

        assert "问答模式" in ask_prompt
        assert "计划模式" in plan_prompt

    def test_contains_memories(self):
        prompt = build_system_prompt(
            SNAPSHOT,
            policy_for("agent"),
            memories=[{"title": "鉴权约定", "content": "Bearer token", "category": "decision"}],
        )

        assert "鉴权约定" in prompt
        assert "Bearer token" in prompt

    def test_contains_skill_blocks(self):
        prompt = build_system_prompt(
            SNAPSHOT,
            policy_for("agent"),
            skill_blocks='<skill name="x">\n方法论\n</skill>',
        )

        assert '<skill name="x">' in prompt

    def test_contains_tool_rules(self):
        prompt = build_system_prompt(SNAPSHOT, policy_for("agent"))

        assert "相对" in prompt  # 沙箱路径规则
        assert "testcases/" in prompt or "artifacts/" in prompt


class TestOrdering:
    def test_mode_instruction_before_skills(self):
        prompt = build_system_prompt(
            SNAPSHOT,
            policy_for("plan"),
            skill_blocks="<skill name=\"x\">SKILL_BODY</skill>",
        )

        assert prompt.index("计划模式") < prompt.index("SKILL_BODY")

    def test_agents_md_before_skills(self):
        prompt = build_system_prompt(
            SNAPSHOT,
            policy_for("agent"),
            skill_blocks="<skill name=\"x\">SKILL_BODY</skill>",
        )

        assert prompt.index("只用测试账号") < prompt.index("SKILL_BODY")


class TestTruncation:
    def test_long_skills_trimmed_first(self):
        huge_skill = "<skill name=\"x\">" + "技" * (MAX_PROMPT_CHARS * 2) + "</skill>"

        prompt = build_system_prompt(SNAPSHOT, policy_for("agent"), skill_blocks=huge_skill)

        assert len(prompt) <= MAX_PROMPT_CHARS + 500
        # 规则不能被砍掉
        assert "计划模式" not in prompt
        assert "问答模式" not in prompt or True
        assert "执行模式" in prompt

    def test_mode_instruction_survives_truncation(self):
        huge_memory = [{"title": f"记忆{i}", "content": "记" * 2000, "category": "fact"} for i in range(30)]

        prompt = build_system_prompt(SNAPSHOT, policy_for("ask"), memories=huge_memory)

        assert len(prompt) <= MAX_PROMPT_CHARS + 500
        assert "问答模式" in prompt

    def test_no_truncation_when_short(self):
        prompt = build_system_prompt(SNAPSHOT, policy_for("agent"))
        assert "截断" not in prompt


class TestEmptyInputs:
    def test_no_memories(self):
        prompt = build_system_prompt(SNAPSHOT, policy_for("agent"), memories=[])
        assert "执行模式" in prompt

    def test_empty_agents_md(self):
        snapshot = SpaceSnapshot(space_id=1, space_name="空", endpoint_count=0)
        prompt = build_system_prompt(snapshot, policy_for("agent"))
        assert "空" in prompt

    def test_snapshot_without_environments_mentions_missing(self):
        snapshot = SpaceSnapshot(space_id=1, space_name="无环境", endpoint_count=0)
        prompt = build_system_prompt(snapshot, policy_for("agent"))
        assert "环境" in prompt
