"""测试执行器模块。

编排单条测试用例的执行流程:
1. 反序列化 TestCase 字段
2. CacheResolver 注入动态参数
3. HttpRequest 发送请求
4. AssertionEngine 执行断言
5. CacheResolver 提取缓存
6. 构造 TestResult 写入数据库
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from src.core.config import AppConfig, get_config

if TYPE_CHECKING:
    from src.core.cache.cache_manager import CacheManager
from src.core.logging import get_logger
from src.data.models.test_case import TestCase
from src.data.models.test_result import TestResult
from src.graph.executor.assertion_engine import AssertionEngine
from src.graph.executor.cache_resolver import CacheResolver
from src.utils.http.request import HttpRequest, split_url
from src.utils.json_utils import safe_json_loads

logger = get_logger(__name__)


class TestExecutor:
    """测试用例执行器。

    负责单条用例的完整执行流程，由 execute_single_tests_node 调用。
    """

    def __init__(self, config: AppConfig | None = None, cache: "CacheManager | None" = None) -> None:
        from src.core.cache.cache_manager import CacheManager

        self.config = config or get_config()
        self.cache_resolver = CacheResolver(cache=cache or CacheManager.get_instance())
        self.assertion_engine = AssertionEngine()

    def execute_single(
        self,
        test_case: TestCase,
        run_id: int,
        session: Session,
    ) -> TestResult:
        """执行单条测试用例。

        Args:
            test_case: ORM TestCase 对象
            run_id: 所属 TestRun ID
            session: 数据库会话

        Returns:
            已持久化的 TestResult 对象
        """
        started_at = datetime.now()

        logger.debug(
            f"[test_executor] 用例开始执行: {test_case.case_id}，{test_case.method} {test_case.url}",
            case_id=test_case.case_id,
            method=test_case.method,
            url=test_case.url,
        )

        headers = safe_json_loads(test_case.headers, {})
        body = safe_json_loads(test_case.body, None)
        params = safe_json_loads(test_case.params, None)
        cache_rules = safe_json_loads(test_case.cache_rules, None)
        assert_rules: list[str] = safe_json_loads(test_case.assert_rules, [])

        if (
            cache_rules
            and self.cache_resolver.has_unresolved_dependencies(cache_rules)
        ):
            logger.info(f"缓存依赖未满足，跳过执行: {test_case.case_id}", case_id=test_case.case_id)
            return self._build_result(
                test_case=test_case,
                run_id=run_id,
                status="skipped",
                started_at=started_at,
                error_message="缓存依赖未满足，跳过执行",
                session=session,
            )

        headers, body, params = self.cache_resolver.inject(headers, body, params, cache_rules)

        response_status_code: int | None = None
        response_headers: dict[str, str] = {}
        response_body: Any = None
        response_time: float = 0.0
        error_message = ""

        try:
            method = test_case.method.upper()
            base_url, endpoint = split_url(test_case.url)
            logger.info(f"拆分出的Base URL: {base_url}，Endpoint: {endpoint}")

            http_client = HttpRequest(
                base_url=base_url,
                connect_timeout=self.config.execution.connect_timeout,
                read_timeout=self.config.execution.read_timeout,
                verify_ssl=True,
            )

            request_kwargs: dict[str, Any] = {}
            if headers:
                request_kwargs["headers"] = headers
            if params:
                request_kwargs["params"] = params
            if body is not None:
                request_kwargs["json"] = body

            request_kwargs["enable_retry"] = True
            request_kwargs["max_retries"] = self.config.execution.retry.max_retries
            request_kwargs["retry_interval"] = int(self.config.execution.retry.retry_interval)

            method_map = {
                "GET": http_client.get,
                "POST": http_client.post,
                "PUT": http_client.put,
                "DELETE": http_client.delete,
                "PATCH": http_client.patch,
            }

            request_func = method_map.get(method)
            if not request_func:
                raise ValueError(f"不支持的 HTTP 方法: {method}")

            response = request_func(endpoint, **request_kwargs)

            if response is not None:
                response_status_code = response.status_code
                response_time = response.elapsed.total_seconds() * 1000
                response_headers = dict(response.headers)
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text

            http_client.close()

        except Exception as e:
            error_message = str(e)
            logger.error(
                f"用例请求失败: {test_case.case_id}，错误: {error_message}",
                case_id=test_case.case_id,
                error=error_message,
            )

        if error_message:
            status = "error"
            assert_results: list[dict[str, Any]] = []
        else:
            all_passed, assert_results = self.assertion_engine.evaluate_all(
                assert_rules, response_body, response_status_code or 0, response_time
            )
            status = "passed" if all_passed else "failed"

        if cache_rules and not error_message:
            self.cache_resolver.extract(response_body, cache_rules)

        finished_at = datetime.now()

        result = self._build_result(
            test_case=test_case,
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            request_url=test_case.url,
            request_method=method,
            request_headers=headers,
            request_body=body,
            query_params=params,
            response_status_code=response_status_code,
            response_headers=response_headers,
            response_body=response_body,
            response_time=response_time,
            error_message=error_message,
            session=session,
        )

        logger.info(
            f"[test_executor] 用例执行完成: {test_case.case_id}，状态: {status}，响应时间: {response_time:.2f}ms",
            case_id=test_case.case_id,
            status=status,
            response_time_ms=round(response_time, 2),
        )

        return result

    def _build_result(
        self,
        test_case: TestCase,
        run_id: int,
        status: str,
        started_at: datetime,
        session: Session,
        finished_at: datetime | None = None,
        request_url: str = "",
        request_method: str = "",
        request_headers: dict | None = None,
        request_body: Any = None,
        query_params: Any = None,
        response_status_code: int | None = None,
        response_headers: dict | None = None,
        response_body: Any = None,
        response_time: float = 0.0,
        error_message: str = "",
    ) -> TestResult:
        """构造 TestResult ORM 对象并写入数据库。"""
        result = TestResult(
            run_id=run_id,
            test_case_id=test_case.id,
            case_id=test_case.case_id,
            case_name=test_case.case_name,
            status=status,
            request_url=request_url,
            request_method=request_method,
            request_headers=json.dumps(request_headers or {}, ensure_ascii=False),
            request_body=json.dumps(request_body, ensure_ascii=False) if request_body is not None else None,
            query_params=json.dumps(query_params, ensure_ascii=False) if query_params is not None else None,
            response_status_code=response_status_code,
            response_headers=json.dumps(response_headers or {}, ensure_ascii=False),
            response_body=self._safe_serialize(response_body),
            response_time=response_time,
            error_message=error_message,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat() if finished_at else None,
        )

        session.add(result)
        return result

    @staticmethod
    def _safe_serialize(data: Any) -> str | None:
        """安全序列化响应体，截断过长内容。"""
        if data is None:
            return None
        try:
            serialized = json.dumps(data, ensure_ascii=False)
            if len(serialized) > 50000:
                return serialized[:50000] + "...(truncated)"
            return serialized
        except (TypeError, ValueError):
            text = str(data)
            if len(text) > 50000:
                return text[:50000] + "...(truncated)"
            return text
