"""单接口测试用例生成节点。

基于 ``BaseCaseGenerationNode`` 模板方法，差异点：
- 按接口逐个调用 LLM 生成用例
- case_id 规则：``{operation_id}_llm_{idx}``
"""

from typing import Any

from data.constant.constants import NodeName
from src.core.logging import get_logger
from src.data.models.endpoint import Endpoint
from src.data.models.test_case import TestCase
from src.data.services import CaseGenerationService
from src.graph.nodes.base_case_generation import BaseCaseGenerationNode
from src.prompts.builders.case_builder import CasePromptBuilder
from src.utils.json_utils import parse_llm_json_response, safe_json_loads

logger = get_logger(__name__)


class GenerateSingleCasesNode(BaseCaseGenerationNode):
    """单接口测试用例生成节点。"""

    run_name_prefix = "LLM测试"
    next_node_on_success = NodeName.EXECUTE_SINGLE_TESTS

    def _generate_cases(
        self,
        *,
        endpoints: list[Endpoint],
        base_url: str,
        run_id: int,
        llm_client: Any,
        case_service: CaseGenerationService,
    ) -> list[TestCase]:
        prompt_builder = CasePromptBuilder()
        cases: list[TestCase] = []

        for endpoint in endpoints:
            try:
                cases.extend(
                    self._generate_for_endpoint(
                        endpoint=endpoint,
                        base_url=base_url,
                        run_id=run_id,
                        prompt_builder=prompt_builder,
                        llm_client=llm_client,
                        case_service=case_service,
                    )
                )
            except Exception as e:
                logger.error(
                    f"接口用例生成失败: {endpoint.name}，错误: {e}",
                    node="generate_single_cases",
                    endpoint=endpoint.name,
                    error=str(e),
                )
        return cases

    @staticmethod
    def _generate_for_endpoint(
        *,
        endpoint: Endpoint,
        base_url: str,
        run_id: int,
        prompt_builder: CasePromptBuilder,
        llm_client: Any,
        case_service: CaseGenerationService,
    ) -> list[TestCase]:
        """为单个 Endpoint 生成测试用例。"""
        full_url = f"{base_url}{endpoint.path}"

        headers = safe_json_loads(endpoint.headers, {})
        body = safe_json_loads(endpoint.body, None)
        params = safe_json_loads(endpoint.params, None)

        default_assert_rules = case_service.extract_default_asserts(endpoint.responses)

        api_info = {
            "name": endpoint.name,
            "url": full_url,
            "method": endpoint.method,
            "headers": headers,
            "body": body,
            "params": params,
            "assert_rules": default_assert_rules,
            "priority": "P1",
            "description": endpoint.description or endpoint.summary or "",
        }

        messages = [
            {"role": "system", "content": prompt_builder.build_system_prompt()},
            {"role": "user", "content": prompt_builder.build_user_prompt(api_info)},
        ]
        response_text = llm_client.chat(messages)
        cases_data = parse_llm_json_response(response_text)

        orm_cases: list[TestCase] = []
        for idx, case_data in enumerate(cases_data, 1):
            orm_cases.append(
                case_service.build_single_case(
                    case_data=case_data,
                    endpoint=endpoint,
                    full_url=full_url,
                    run_id=run_id,
                    idx=idx,
                    default_assert_rules=default_assert_rules,
                )
            )
        return orm_cases


generate_single_cases_node = GenerateSingleCasesNode()
