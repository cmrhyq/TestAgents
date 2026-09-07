"""用例生成节点基类（模板方法）。

single / flow 两个生成节点共享约 80% 的编排逻辑：
validate → load(space/endpoints) → create_run → generate → persist。

子类只需实现 ``_generate_cases``（差异：PromptBuilder、是否按接口循环、case_id 规则）。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from src.core.config import get_config
from src.core.database.database_manager import get_db_manager
from src.core.llm.llm_gateway import get_llm_gateway
from src.core.logging import get_logger
from src.data.models.endpoint import Endpoint
from src.data.models.test_case import TestCase
from src.data.services import CaseGenerationService, EndpointService, SpaceService
from data.constant.constants import NodeName
from src.graph.state import AgentState
from src.core.database.database_manager import init_database_from_config

logger = get_logger(__name__)


class BaseCaseGenerationNode(ABC):
    """用例生成节点模板方法。

    Attributes:
        run_name_prefix: 执行批次名称前缀（single/flow 区分）
        next_node_on_success: 生成成功后的下一跳节点
    """

    run_name_prefix: str = ""
    next_node_on_success: NodeName = NodeName.GENERATE_REPORT

    @abstractmethod
    def _generate_cases(
        self,
        *,
        endpoints: list[Endpoint],
        base_url: str,
        run_id: int,
        llm_client: Any,
        case_service: CaseGenerationService,
    ) -> list[TestCase]:
        """子类实现：调用 LLM 生成并构造 TestCase ORM 列表。"""

    def __call__(self, state: AgentState) -> dict:
        """模板方法：校验 → 加载空间/接口 → 创建批次 → 生成 → 持久化。"""
        selected_endpoints = state.get("selected_endpoints", [])
        logger.info(
            f"进入用例生成节点，接口数: {len(selected_endpoints)}",
            node=self.__class__.__name__,
            endpoint_count=len(selected_endpoints),
        )

        if not selected_endpoints:
            return self._error("无选中的接口")

        config = get_config()
        llm_client = get_llm_gateway()

        space_id = int(selected_endpoints[0].get("space_id") or 0)
        endpoint_ids = [int(ep["endpoint_id"]) for ep in selected_endpoints if ep.get("endpoint_id")]

        init_database_from_config()
        with get_db_manager().get_session() as session:
            space_service = SpaceService(session)
            endpoint_service = EndpointService(session)
            case_service = CaseGenerationService(session)

            space = space_service.get_space(space_id)
            if not space:
                return self._error(f"空间不存在: space_id={space_id}")

            endpoints: list[Endpoint] = endpoint_service.get_active_by_ids(endpoint_ids)
            if not endpoints:
                return self._error("未查询到有效的接口定义")

            base_url = space.base_url.rstrip("/")
            run = case_service.create_running_run(
                space_id=space_id,
                name=f"{self.run_name_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                model=config.llm.default_model,
            )
            run_id = run.id

            cases = self._generate_cases(
                endpoints=endpoints,
                base_url=base_url,
                run_id=run_id,
                llm_client=llm_client,
                case_service=case_service,
            )
            total_cases = case_service.persist_cases(cases)
            case_service.update_run_total(run_id, total_cases)
            logger.info(
                f"用例生成完成 - run_id: {run_id}, 总用例数: {total_cases}",
                node=self.__class__.__name__,
                run_id=run_id,
                total_cases=total_cases,
            )

        return {"run_id": run_id, "test_cases_count": total_cases, "next_node": self.next_node_on_success.value}

    @staticmethod
    def _error(message: str) -> dict:
        """统一错误返回。"""
        return {
            "run_id": 0,
            "test_cases_count": 0,
            "error_message": message,
            "next_node": NodeName.ERROR.value,
        }
