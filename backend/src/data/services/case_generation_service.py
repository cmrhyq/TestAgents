"""测试用例生成服务。

承接用例生成节点的 ORM 构造与持久化：
- ``create_running_run``：创建 running 状态的执行批次（时间戳统一 ``local_now``）
- ``build_single_case`` / ``build_flow_case``：从 LLM 输出构造 TestCase ORM
- ``persist_cases``：批量落库
- ``update_run_total``：回写批次用例总数
"""

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from src.data.enum.workflow import TestStatus
from src.data.models.base import local_now
from src.data.models.endpoint import Endpoint
from src.data.models.test_case import TestCase
from src.data.models.test_run import TestRun
from src.data.repositories import TestCaseRepository, TestRunRepository


class CaseGenerationService:
    """用例生成领域服务。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.case_repo = TestCaseRepository(session)
        self.run_repo = TestRunRepository(session)

    def create_running_run(
        self,
        space_id: int,
        name: str,
        model: str,
    ) -> TestRun:
        """创建 running 状态的执行批次。"""
        run = TestRun(
            space_id=space_id,
            name=name,
            status=TestStatus.RUNNING.value,
            trigger_type="manual",
            llm_model=model,
            started_at=local_now(),
        )
        return self.run_repo.add(run)

    def persist_cases(self, cases: list[TestCase]) -> int:
        """批量落库用例，返回数量。"""
        if not cases:
            return 0
        self.case_repo.add_many(cases)
        return len(cases)

    def update_run_total(self, run_id: int, total: int) -> None:
        """回写批次用例总数。"""
        self.run_repo.update_fields(run_id, total_cases=total)

    def build_single_case(
        self,
        case_data: dict[str, Any],
        endpoint: Endpoint,
        full_url: str,
        run_id: int,
        idx: int,
        default_assert_rules: list[str],
    ) -> TestCase:
        """从 LLM 输出的单条用例数据构造 TestCase ORM 对象。"""
        case_name = case_data.get("case_name", f"{endpoint.name}_case_{idx:03d}")
        scenario_type = case_data.get("scenario_type", "normal")
        priority = case_data.get("priority", "P1")
        case_headers = case_data.get("headers", {})
        case_body = case_data.get("body")
        case_params = case_data.get("params")
        assert_rules = case_data.get("assert_rules", default_assert_rules)
        expected_result = case_data.get("expected_result", "成功")
        description = case_data.get("description", "")
        cache_rules = case_data.get("cache_rules")

        case_id = f"{endpoint.operation_id}_llm_{idx:03d}"

        body_str = json.dumps(case_body, ensure_ascii=False) if case_body is not None else None
        unique_content = f"{full_url}|{endpoint.method}|{body_str or ''}"
        unique_hash = hashlib.md5(unique_content.encode()).hexdigest()[:8]

        return TestCase(
            run_id=run_id,
            endpoint_id=endpoint.id,
            case_id=case_id,
            case_name=case_name,
            url=full_url,
            method=endpoint.method,
            scenario_type=scenario_type
            if scenario_type
            in ("normal", "param_missing", "param_type_error", "boundary_value", "permission_error", "custom")
            else "custom",
            priority=priority if priority in ("P0", "P1", "P2") else "P1",
            headers=json.dumps(case_headers, ensure_ascii=False),
            body=body_str,
            params=json.dumps(case_params, ensure_ascii=False) if case_params else None,
            cache_rules=json.dumps(cache_rules, ensure_ascii=False) if cache_rules else None,
            assert_rules=json.dumps(assert_rules, ensure_ascii=False),
            expected_result=expected_result,
            description=description,
            remark="LLM生成",
            unique_hash=unique_hash,
            generated_by="llm",
        )

    def build_flow_case(
        self,
        case_data: dict[str, Any],
        endpoint: Endpoint,
        full_url: str,
        run_id: int,
        idx: int,
    ) -> TestCase:
        """从 LLM 输出的单步流程用例数据构造 TestCase ORM 对象。"""
        step_order = case_data.get("step_order", idx)
        case_name = case_data.get("case_name", f"flow_step_{step_order:03d}_{endpoint.name}")
        scenario_type = case_data.get("scenario_type", "normal")
        priority = case_data.get("priority", "P0")
        case_headers = case_data.get("headers", {})
        case_body = case_data.get("body")
        case_params = case_data.get("params")
        assert_rules = case_data.get("assert_rules", ["status_code == 200"])
        expected_result = case_data.get("expected_result", "成功")
        description = case_data.get("description", "")
        cache_rules = case_data.get("cache_rules")

        case_id = f"{endpoint.operation_id}_flow_{step_order:03d}"

        body_str = json.dumps(case_body, ensure_ascii=False) if case_body is not None else None
        unique_content = f"flow|{full_url}|{endpoint.method}|{step_order}|{body_str or ''}"
        unique_hash = hashlib.md5(unique_content.encode()).hexdigest()[:8]

        return TestCase(
            run_id=run_id,
            endpoint_id=endpoint.id,
            case_id=case_id,
            case_name=case_name,
            url=full_url,
            method=endpoint.method,
            scenario_type=scenario_type
            if scenario_type
            in ("normal", "param_missing", "param_type_error", "boundary_value", "permission_error", "custom")
            else "normal",
            priority=priority if priority in ("P0", "P1", "P2") else "P0",
            headers=json.dumps(case_headers, ensure_ascii=False),
            body=body_str,
            params=json.dumps(case_params, ensure_ascii=False) if case_params else None,
            cache_rules=json.dumps(cache_rules, ensure_ascii=False) if cache_rules else None,
            assert_rules=json.dumps(assert_rules, ensure_ascii=False),
            expected_result=expected_result,
            description=description,
            remark=f"LLM流程生成-步骤{step_order}",
            unique_hash=unique_hash,
            generated_by="llm",
        )

    @staticmethod
    def extract_default_asserts(responses_json: str | None) -> list[str]:
        """从 Endpoint.responses 字段提取默认断言规则。"""
        default_rules = ["status_code == 200"]

        if not responses_json:
            return default_rules

        try:
            responses = json.loads(responses_json)
        except (json.JSONDecodeError, TypeError):
            return default_rules

        if not responses:
            return default_rules

        for resp in responses:
            status_code = str(resp.get("status_code", ""))
            if status_code.startswith("2"):
                default_rules = [f"status_code == {status_code}"]
                content = resp.get("content", {})
                if content:
                    for media_data in content.values():
                        schema = media_data.get("schema", {})
                        props = schema.get("properties", {})
                        if "code" in props:
                            default_rules.append("$.code == 200")
                        break
                break

        return default_rules
