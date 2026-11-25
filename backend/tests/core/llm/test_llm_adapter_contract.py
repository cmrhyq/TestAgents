"""LLM 适配器契约：真实 langchain-litellm 适配器 + 假 Router。

这两条行为只有在适配器真实参与时才暴露，注入假 chat model 的测试永远看不到：

1. ``LLMService`` 必须让 Router 走流式接口，而不是回退 ``ainvoke``，
   否则 SSE 只下发一个整体分片，首字节延迟等于整段生成时间；
2. litellm 预路由就地写入 ``metadata`` 的 ``deployment`` / ``routing_decision``
   必须落到 ``response_metadata``，否则 ``llm_log`` 记成路由组名、成本为 NULL。

假 Router 只模拟 litellm 一侧的契约（就地写 metadata、按流返回 chunk），
不替换被测的适配层本身。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage
from litellm.types.utils import Usage

from src.core.config import AppConfig
from src.core.llm.llm_service import LLMService
from src.data.models.llm_log import LLMLog

ROUTE_GROUP = "smart-router"
DEPLOYMENT = "deepseek/deepseek-v4-flash"
ROUTED_MODEL = "deepseek-v4-flash"
SPACE_ID = 9201
CONVERSATION_ID = 9202
MODEL_LIST = [{"model_name": ROUTE_GROUP, "litellm_params": {"model": "auto_router/complexity_router"}}]


class FakeRouter:
    """litellm Router 替身：模拟预路由写 metadata 与两种返回形态。"""

    model_list = MODEL_LIST

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _stamp(metadata: Any) -> None:
        """模拟 litellm 选路阶段就地补全 metadata。"""
        if isinstance(metadata, dict):
            metadata.update(
                {
                    "model_group": ROUTE_GROUP,
                    "deployment": DEPLOYMENT,
                    "deployment_model_name": ROUTE_GROUP,
                    "routing_decision": {
                        "router_type": "complexity",
                        "routed_model": ROUTED_MODEL,
                        "tier": "SIMPLE",
                        "cause": "heuristic_scorer",
                    },
                }
            )

    async def acompletion(self, messages: Any = None, **kwargs: Any) -> Any:
        """按 ``stream`` 参数返回异步流或完整响应。"""
        self.calls.append(kwargs)
        self._stamp(kwargs.get("metadata"))

        if not kwargs.get("stream"):
            return {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "完整回答"},
                        "finish_reason": "stop",
                    }
                ],
                "model": "deepseek-chat",
                "usage": Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
            }

        async def _stream() -> AsyncIterator[dict[str, Any]]:
            for text in ("你", "好", "呀"):
                yield {
                    "id": "chatcmpl-1",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
                    "model": "deepseek-chat",
                }
            # 真实 provider 把 usage 放在末尾 choices 为空的分片
            yield {
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "choices": [],
                "model": "deepseek-chat",
                "usage": Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
            }

        return _stream()


def _service(session_scope, router: FakeRouter) -> LLMService:
    """构造注入了假 Router 的服务实例；模型实例由 ``model`` 属性真实构建。"""
    config = AppConfig(llm={"default_model": ROUTE_GROUP}, model_list=MODEL_LIST)
    service = LLMService(config, session_scope=session_scope)
    service._router = router  # type: ignore[assignment]
    return service


def _rows(session_scope) -> list[LLMLog]:
    """读取全部统计行。"""
    with session_scope() as session:
        return list(session.query(LLMLog).order_by(LLMLog.created_at).all())


async def _drain(agen) -> list:
    """把异步流收成列表。"""
    return [item async for item in agen]


class TestStreaming:
    """流式路径：必须真的流，并且每个分片都带归因。"""

    def test_model_is_constructed_as_streaming(self, session_scope):
        """``streaming=False`` 会让 langchain-core 回退 ainvoke，这里锁住配置。"""
        service = _service(session_scope, FakeRouter())

        assert service.model.streaming is True

    async def test_router_receives_streaming_request(self, session_scope):
        router = FakeRouter()
        service = _service(session_scope, router)

        chunks = [chunk async for chunk in service.astream_with_tools([HumanMessage(content="q")], [])]

        assert router.calls[0]["stream"] is True
        assert len(chunks) > 1
        assert "".join(str(chunk.content) for chunk in chunks) == "你好呀"

    async def test_chunks_carry_deployment_and_tier(self, session_scope):
        service = _service(session_scope, FakeRouter())

        chunks = [chunk async for chunk in service.astream_with_tools([HumanMessage(content="q")], [])]

        metadata = chunks[0].response_metadata
        assert metadata["deployment"] == DEPLOYMENT
        assert metadata["routing_decision"]["tier"] == "SIMPLE"

    async def test_llm_log_records_deployment_tier_and_cost(self, session_scope):
        router = FakeRouter()
        service = _service(session_scope, router)

        stream = service.astream_with_tools(
            [HumanMessage(content="q")],
            [],
            space_id=SPACE_ID,
            conversation_id=CONVERSATION_ID,
        )
        await _drain(stream)

        row = _rows(session_scope)[0]
        assert row.model_name == DEPLOYMENT
        assert row.model_name != ROUTE_GROUP
        assert row.provider == "deepseek"
        assert row.routing_tier == "SIMPLE"
        assert row.cost_usd is not None and row.cost_usd > 0
        assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (1000, 500, 1500)
        assert (row.space_id, row.conversation_id) == (SPACE_ID, CONVERSATION_ID)


class TestNonStreaming:
    """显式 ``stream=False`` 时，非流式响应同样要带归因。"""

    async def test_explicit_non_stream_still_attributes(self, session_scope):
        service = _service(session_scope, FakeRouter())

        response = await service.ainvoke([HumanMessage(content="q")], stream=False)

        assert response.response_metadata["deployment"] == DEPLOYMENT
        assert response.response_metadata["routing_decision"]["tier"] == "SIMPLE"
        row = _rows(session_scope)[0]
        assert row.model_name == DEPLOYMENT
        assert row.provider == "deepseek"
