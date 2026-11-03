"""LLM 调用统计（`llm_log`）的字段契约。

归因字段需落库；`model_name` 记真实 deployment 而非 Router 的 model_group；
定价未知时 `cost_usd` 为 NULL，记录为 0 会被当作免费。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from contextlib import contextmanager

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import AppConfig
from src.core.llm.llm_service import LLMService
from src.data.models.base import Base
from src.data.models.llm_log import LLMLog

SPACE_ID = 7001
CONVERSATION_ID = 8001


@pytest.fixture()
def session_scope(tmp_path):
    """临时 SQLite 库，避免统计写入真实 db/TestAgents.db。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'usage.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _scope() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    yield _scope
    engine.dispose()


def _config() -> AppConfig:
    """构造含一个具体模型与一个 Router 的配置。"""
    return AppConfig(
        model_list=[
            {"model_name": "glm-4-flash", "litellm_params": {"model": "zai/glm-4-flash"}},
            {"model_name": "smart-router", "litellm_params": {"model": "auto_router/complexity_router"}},
        ]
    )


class FakeStreamModel:
    """可编排的流式模型：按给定 chunk 列表产出，支持 bind_tools。"""

    def __init__(self, chunks: list[AIMessageChunk], *, boom: bool = False) -> None:
        self._chunks = chunks
        self._boom = boom
        self.bound_tools: list[str] | None = None

    def bind_tools(self, tools):
        self.bound_tools = [getattr(t, "name", str(t)) for t in tools]
        return self

    async def astream(self, messages, **kwargs) -> AsyncIterator[AIMessageChunk]:
        if self._boom:
            raise RuntimeError("provider exploded")
        for chunk in self._chunks:
            yield chunk


def _chunk(
    text: str = "",
    *,
    usage: dict | None = None,
    deployment: str = "zai/glm-4-flash",
    tier: str = "SIMPLE",
) -> AIMessageChunk:
    """构造带 usage 与路由元数据的分片。"""
    meta: dict = {"model_group": "smart-router", "deployment": deployment}
    if tier:
        meta["routing_decision"] = {"routed_model": deployment.split("/")[-1], "tier": tier}
    return AIMessageChunk(
        content=text,
        usage_metadata=usage,  # type: ignore[arg-type]
        response_metadata=meta,
    )


def _service(session_scope, model) -> LLMService:
    """构造注入了假模型的服务实例。"""
    service = LLMService(_config(), session_scope=session_scope)
    service._model = model  # 绕过 litellm Router，直接注入假模型
    return service


def _rows(session_scope) -> list[LLMLog]:
    """按创建时间读取全部统计行。"""
    with session_scope() as session:
        return list(session.query(LLMLog).order_by(LLMLog.created_at).all())


async def _drain(agen) -> list:
    """把异步流收成列表。"""
    return [item async for item in agen]


class TestAttribution:
    """归因字段落库，且允许缺省。"""

    async def test_records_space_and_conversation(self, session_scope):
        service = _service(session_scope, FakeStreamModel([_chunk("hi")]))

        await _drain(
            service.astream_with_tools(
                [HumanMessage(content="q")],
                [],
                space_id=SPACE_ID,
                conversation_id=CONVERSATION_ID,
            )
        )

        rows = _rows(session_scope)
        assert len(rows) == 1
        assert rows[0].space_id == SPACE_ID
        assert rows[0].conversation_id == CONVERSATION_ID

    async def test_attribution_is_optional(self, session_scope):
        """非对话链路不传归因时不得报错。"""
        service = _service(session_scope, FakeStreamModel([_chunk("hi")]))

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        row = _rows(session_scope)[0]
        assert row.space_id is None
        assert row.conversation_id is None

    async def test_multiple_rounds_write_multiple_rows(self, session_scope):
        """ReAct 每轮均为一次真实计费调用，各记一条。"""
        service = _service(session_scope, FakeStreamModel([_chunk("hi")]))

        for _ in range(3):
            await _drain(
                service.astream_with_tools(
                    [HumanMessage(content="q")], [], space_id=SPACE_ID, conversation_id=CONVERSATION_ID
                )
            )

        assert len(_rows(session_scope)) == 3


class TestModelName:
    """记录真实命中的 deployment，而非 Router 的 model_group。"""

    async def test_uses_deployment_not_model_group(self, session_scope):
        service = _service(session_scope, FakeStreamModel([_chunk("hi")]))

        await _drain(service.astream_with_tools([HumanMessage(content="q")], [], space_id=SPACE_ID))

        row = _rows(session_scope)[0]
        assert row.model_name == "zai/glm-4-flash"
        assert row.model_name != "smart-router"
        assert row.provider == "zai"

    async def test_falls_back_to_routed_model(self, session_scope):
        """`deployment` 缺失时回退到 `routing_decision.routed_model`。"""
        chunk = AIMessageChunk(
            content="hi",
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},  # type: ignore[arg-type]
            response_metadata={"model_group": "smart-router", "routing_decision": {"routed_model": "deepseek-v4-flash"}},
        )
        service = _service(session_scope, FakeStreamModel([chunk]))

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        assert _rows(session_scope)[0].model_name == "deepseek-v4-flash"

    async def test_routing_tier_recorded(self, session_scope):
        service = _service(session_scope, FakeStreamModel([_chunk("hi", tier="REASONING")]))

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        assert _rows(session_scope)[0].routing_tier == "REASONING"


class TestUsage:
    """token 与耗时采集。"""

    async def test_tokens_recorded(self, session_scope):
        service = _service(
            session_scope,
            FakeStreamModel([_chunk("h"), _chunk("i", usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18})]),
        )

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        row = _rows(session_scope)[0]
        assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (11, 7, 18)

    async def test_usage_on_intermediate_chunk_is_captured(self, session_scope):
        """部分 provider 把 usage 放在中间分片，需扫描全部分片。"""
        service = _service(
            session_scope,
            FakeStreamModel(
                [
                    _chunk("a", usage={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}),
                    _chunk("b"),
                    _chunk("c"),
                ]
            ),
        )

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        assert _rows(session_scope)[0].total_tokens == 7

    async def test_duration_recorded(self, session_scope):
        service = _service(session_scope, FakeStreamModel([_chunk("hi")]))

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        assert _rows(session_scope)[0].duration_ms >= 0


class TestCost:
    """成本：可算则算，定价未知留 NULL。"""

    async def test_cost_computed_for_known_pricing(self, session_scope):
        service = _service(
            session_scope,
            FakeStreamModel(
                [
                    _chunk(
                        "hi",
                        usage={"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000},
                        deployment="deepseek/deepseek-v4-flash",
                    )
                ]
            ),
        )

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        cost = _rows(session_scope)[0].cost_usd
        assert cost is not None and cost > 0

    async def test_cost_is_none_when_pricing_unknown(self, session_scope):
        """zai 不在 litellm 定价表内，须为 NULL 而非 0。"""
        service = _service(session_scope, FakeStreamModel([_chunk("hi")]))

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        assert _rows(session_scope)[0].cost_usd is None


class TestPricingLookup:
    """定价查表与 provider 前缀处理。"""

    def test_unknown_model_returns_none(self):
        from src.core.llm.llm_service import _estimate_cost

        assert _estimate_cost("zai/glm-4-flash", 1000, 100) is None

    def test_known_model_returns_positive(self):
        from src.core.llm.llm_service import _estimate_cost

        cost = _estimate_cost("deepseek/deepseek-v4-flash", 1_000_000, 1_000_000)
        assert cost is not None and cost > 0

    def test_lookup_handles_provider_prefix(self, monkeypatch):
        """带 provider 前缀与裸名都需命中。"""
        from src.core.llm import llm_service

        fake_map = {"deepseek-v4-flash": {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6}}
        monkeypatch.setattr("litellm.model_cost", fake_map, raising=False)

        assert llm_service._lookup_pricing("deepseek/deepseek-v4-flash") is fake_map["deepseek-v4-flash"]
        assert llm_service._lookup_pricing("deepseek-v4-flash") is fake_map["deepseek-v4-flash"]
        assert llm_service._lookup_pricing("zai/glm-4-flash") is None

    def test_explicitly_free_model_reports_zero(self, monkeypatch):
        """本地模型定价显式为 0 时成本为 0.0，与定价未知区分。"""
        from src.core.llm.llm_service import _estimate_cost

        monkeypatch.setattr(
            "litellm.model_cost",
            {"ollama/llama3": {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0}},
            raising=False,
        )

        assert _estimate_cost("ollama/llama3", 1000, 100) == 0.0

    def test_zero_tokens_returns_none(self):
        from src.core.llm.llm_service import _estimate_cost

        assert _estimate_cost("deepseek/deepseek-v4-flash", 0, 0) is None


class TestCustomPricing:
    """`config.pricing` 让 litellm 未收录的模型也能计价。"""

    def test_custom_pricing_prices_unmapped_model(self):
        from src.core.llm.llm_service import _estimate_cost

        pricing = [{"model": "zai/glm-4-flash", "input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6}]

        # 无自定义费率时未知
        assert _estimate_cost("zai/glm-4-flash", 1000, 500) is None
        # 补上费率后可算
        assert _estimate_cost("zai/glm-4-flash", 1000, 500, pricing) == pytest.approx(0.002)

    def test_custom_pricing_takes_precedence(self, monkeypatch):
        from src.core.llm.llm_service import _estimate_cost

        monkeypatch.setattr(
            "litellm.model_cost",
            {"x-model": {"input_cost_per_token": 1e-9, "output_cost_per_token": 1e-9}},
            raising=False,
        )
        pricing = [{"model": "vendor/x-model", "input_cost_per_token": 1e-6, "output_cost_per_token": 0.0}]

        # 自定义 1e-6 覆盖内置 1e-9
        assert _estimate_cost("vendor/x-model", 1_000_000, 0, pricing) == pytest.approx(1.0)

    def test_pydantic_pricing_entries_supported(self):
        """配置为 `ModelPricing` 对象而非 dict 时同样生效。"""
        from src.core.config import ModelPricing
        from src.core.llm.llm_service import _estimate_cost

        pricing = [ModelPricing(model="zai/glm-4-flash", input_cost_per_token=1e-6, output_cost_per_token=0.0)]

        assert _estimate_cost("zai/glm-4-flash", 1_000_000, 0, pricing) == pytest.approx(1.0)


class TestFailure:
    """失败调用同样留痕，否则成本统计会漏掉报错调用。"""

    async def test_failure_recorded_and_reraised(self, session_scope):
        service = _service(session_scope, FakeStreamModel([], boom=True))

        with pytest.raises(RuntimeError):
            await _drain(service.astream_with_tools([HumanMessage(content="q")], [], space_id=SPACE_ID))

        row = _rows(session_scope)[0]
        assert row.success == 0
        assert "exploded" in row.error_message
        assert row.space_id == SPACE_ID


class TestToolsBinding:
    """工具必须绑定到模型上，不能因更换入口而丢失。"""

    async def test_tools_are_bound(self, session_scope):
        model = FakeStreamModel([_chunk("hi")])
        service = _service(session_scope, model)

        class Tool:
            name = "read_file"

        await _drain(service.astream_with_tools([HumanMessage(content="q")], [Tool()]))

        assert model.bound_tools == ["read_file"]

    async def test_empty_tools_skips_binding(self, session_scope):
        """部分 provider 拒绝空 tools 数组，空列表时不调用 `bind_tools`。"""
        model = FakeStreamModel([_chunk("hi")])
        service = _service(session_scope, model)

        await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        assert model.bound_tools is None

    async def test_chunks_are_passed_through(self, session_scope):
        service = _service(session_scope, FakeStreamModel([_chunk("你"), _chunk("好")]))

        chunks = await _drain(service.astream_with_tools([HumanMessage(content="q")], []))

        assert "".join(c.content for c in chunks) == "你好"
