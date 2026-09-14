"""generate_single_cases_node 单元测试。

覆盖 CasePromptBuilder 路径：mock LLM 客户端，走完整 _generate_for_endpoint。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.graph.nodes.generate_single_cases_node import GenerateSingleCasesNode
from src.prompts.builders.case_builder import CasePromptBuilder

VALID_RESPONSE = (
    '{"test_cases": ['
    '{"case_name": "正常登录", "scenario_type": "normal", "priority": "P0", '
    '"headers": {"Content-Type": "application/json"}, "body": {"username": "admin", "password": "123456"}, '
    '"assert_rules": ["status_code == 200", "$.code == 200"], "expected_result": "成功", "description": "正常登录"},'
    '{"case_name": "缺少密码", "scenario_type": "param_missing", "priority": "P1", '
    '"headers": {"Content-Type": "application/json"}, "body": {"username": "admin"}, '
    '"assert_rules": ["status_code == 400"], "expected_result": "失败", "description": "移除密码"}'
    "]}"
)


def _make_endpoint() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="用户登录",
        path="/api/v1/login",
        method="POST",
        headers='{"Content-Type": "application/json"}',
        body='{"username": "admin", "password": "123456"}',
        params=None,
        responses='[{"status_code": 200, "content": {"application/json": {"schema": {"type": "object"}}}}]',
        operation_id="login",
        description="用户登录接口",
        summary="登录",
    )


def _make_case_service() -> MagicMock:
    service = MagicMock()
    service.extract_default_asserts.return_value = ["status_code == 200"]
    return service


def _run(endpoint, llm_client, case_service):
    return GenerateSingleCasesNode._generate_for_endpoint(
        endpoint=endpoint,
        base_url="https://api.example.com",
        run_id=1,
        prompt_builder=CasePromptBuilder(),
        llm_client=llm_client,
        case_service=case_service,
    )


@pytest.mark.unit
class TestGenerateSingleCasesNode:
    def test_valid_output_builds_cases(self):
        llm = MagicMock()
        llm.chat.return_value = VALID_RESPONSE
        case_service = _make_case_service()

        cases = _run(_make_endpoint(), llm, case_service)

        assert llm.chat.call_count == 1
        assert case_service.build_single_case.call_count == 2
        assert len(cases) == 2

    def test_invalid_json_returns_no_cases(self):
        llm = MagicMock()
        llm.chat.return_value = "这不是JSON"
        case_service = _make_case_service()

        cases = _run(_make_endpoint(), llm, case_service)

        assert llm.chat.call_count == 1
        assert case_service.build_single_case.call_count == 0
        assert cases == []

    def test_messages_use_case_prompt_builder(self):
        llm = MagicMock()
        llm.chat.return_value = VALID_RESPONSE

        _run(_make_endpoint(), llm, _make_case_service())

        messages = llm.chat.call_args.args[0]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "API名称: 用户登录" in messages[1]["content"]
        assert "API地址: https://api.example.com/api/v1/login" in messages[1]["content"]
