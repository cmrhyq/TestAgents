"""工作模式策略测试。

模式的**唯一强制点**是工具白名单——prompt 里写「请不要调用写接口」只是建议，
模型在工具列表里有 `send_request` 时迟早会调。所以这里的测试是模式的真正验收。
"""

import pytest

from src.agent.modes import (
    DEFAULT_MAX_STEPS,
    PLAN_MAX_STEPS,
    Mode,
    filter_tools,
    normalize_mode,
    policy_for,
)


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


ALL_TOOLS = [
    FakeTool("search_space"),
    FakeTool("get_space_endpoints"),
    FakeTool("read_file"),
    FakeTool("send_request"),
    FakeTool("write_file"),
    FakeTool("remember"),
]


class TestModeNormalize:
    def test_lowercase(self):
        assert normalize_mode("agent") is Mode.AGENT
        assert normalize_mode("ask") is Mode.ASK
        assert normalize_mode("plan") is Mode.PLAN

    def test_case_insensitive(self):
        assert normalize_mode("ASK") is Mode.ASK

    def test_legacy_run_maps_to_agent(self):
        assert normalize_mode("Run") is Mode.AGENT

    def test_none_defaults_to_agent(self):
        assert normalize_mode(None) is Mode.AGENT
        assert normalize_mode("") is Mode.AGENT

    def test_unknown_falls_back_to_agent(self):
        assert normalize_mode("whatever") is Mode.AGENT


class TestPolicy:
    def test_ask_has_no_side_effects(self):
        assert policy_for("ask").allow_side_effects is False

    def test_plan_has_no_side_effects(self):
        assert policy_for("plan").allow_side_effects is False

    def test_agent_allows_side_effects(self):
        assert policy_for("agent").allow_side_effects is True

    def test_plan_has_own_instruction(self):
        policy = policy_for("plan")
        assert "计划" in policy.instruction
        assert policy.max_steps == PLAN_MAX_STEPS

    def test_ask_instruction_forbids_execution(self):
        policy = policy_for("ask")
        assert "不要" in policy.instruction or "只回答" in policy.instruction

    def test_agent_default_steps(self):
        assert policy_for("agent").max_steps == DEFAULT_MAX_STEPS

    def test_policy_exposes_label(self):
        assert policy_for("ask").label == "问答"
        assert policy_for("plan").label == "计划"
        assert policy_for("agent").label == "执行"


class TestFilterTools:
    def test_ask_removes_side_effect_tools(self):
        kept = filter_tools(ALL_TOOLS, policy_for("ask"))

        names = {t.name for t in kept}
        assert "read_file" in names
        assert "send_request" not in names
        assert "write_file" not in names
        assert "remember" not in names

    def test_plan_removes_side_effect_tools(self):
        names = {t.name for t in filter_tools(ALL_TOOLS, policy_for("plan"))}
        assert "send_request" not in names
        assert "write_file" not in names

    def test_agent_keeps_everything(self):
        assert len(filter_tools(ALL_TOOLS, policy_for("agent"))) == len(ALL_TOOLS)

    def test_skill_allowed_tools_narrows(self):
        """skill 只能收窄权限，不能放大。"""
        kept = filter_tools(ALL_TOOLS, policy_for("agent"), skill_allowed={"read_file", "send_request"})

        assert {t.name for t in kept} == {"read_file", "send_request"}

    def test_skill_cannot_reintroduce_blocked_tool(self):
        """ask 模式下，即使 skill 声明了 send_request 也不能拿到。"""
        kept = filter_tools(ALL_TOOLS, policy_for("ask"), skill_allowed={"read_file", "send_request"})

        assert {t.name for t in kept} == {"read_file"}

    def test_empty_skill_set_yields_nothing(self):
        assert filter_tools(ALL_TOOLS, policy_for("agent"), skill_allowed=set()) == []

    def test_unknown_tool_name_is_kept_by_default(self):
        """新增工具没登记时不应被静默丢弃（否则调了半天找不到原因）。"""
        tools = [FakeTool("brand_new_tool")]
        assert len(filter_tools(tools, policy_for("ask"))) == 1


class TestSideEffectRegistry:
    def test_known_side_effect_names(self):
        from src.agent.modes import SIDE_EFFECT_TOOL_NAMES

        assert {"send_request", "write_file", "delete_file", "remember", "forget"} <= SIDE_EFFECT_TOOL_NAMES

    def test_read_only_names_dont_overlap(self):
        from src.agent.modes import READ_ONLY_TOOL_NAMES, SIDE_EFFECT_TOOL_NAMES

        assert not (READ_ONLY_TOOL_NAMES & SIDE_EFFECT_TOOL_NAMES)
