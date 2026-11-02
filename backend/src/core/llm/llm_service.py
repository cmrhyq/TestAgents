import os

# 只用随包分发的本地定价表，不向 GitHub 拉远端 cost map。
# 两个原因：① 离线/内网环境会阻塞到超时；② 远端表与本地表条目不一致时，
# 同一模型算出的成本会在「异常」「0.0」之间漂移——而 0.0 会被读成「免费」。
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

from collections.abc import AsyncIterator, Callable, Iterator  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from contextlib import AbstractContextManager, contextmanager  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from time import perf_counter  # noqa: E402
from typing import Any  # noqa: E402

import asyncio  # noqa: E402

from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402
from langchain_litellm import ChatLiteLLMRouter  # noqa: E402
from litellm import Router  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.core.config import AppConfig, get_config  # noqa: E402
from src.core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)

#: 会话上下文工厂；注入后统计可写临时库，单测不必启动整个应用
SessionScope = Callable[[], AbstractContextManager[Session]]


def _default_session_scope() -> SessionScope:
    """默认从全局数据库管理器取会话（惰性，构造时不会触发 DB 初始化）。"""

    @contextmanager
    def _scope() -> Iterator[Session]:
        from src.core.database.database_manager import init_database_from_config

        with init_database_from_config().get_session() as session:
            yield session

    return _scope


def _run_async(coro) -> Any:
    """在同步上下文中执行协程。

    litellm 的 auto_router/complexity_router（smart-router）只在
    ``Router.acompletion`` 的 async pre-routing hook 中生效；同步
    ``Router.completion`` 会把 auto_router/complexity_router 当普通
    provider 直接抛 Unmapped LLM provider。因此同步入口必须桥接到
    async 路径：

    - 当前线程无事件循环：直接 ``asyncio.run``
    - 当前线程已有事件循环（如误在 async 函数中调同步方法）：
      丢到新线程执行，避免 RuntimeError
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


class LLMService:
    """基于 LiteLLM Router 的统一 LLM 服务。

    内部持有 ``ChatLiteLLMRouter``（LangChain BaseChatModel），
    由 ``litellm.Router`` + ``config.model_list`` 驱动多模型路由。

    All methods take ``list[BaseMessage]`` and return ``AIMessage`` or ``AIMessageChunk``.

    Args:
        config: 应用配置，为 None 时使用全局配置。
        session_scope: 统计落库用的会话工厂；None 时用全局数据库单例。
            显式注入是为了单测能跑在临时库上。

    Raises:
        ValueError: ``config.model_list`` 为空时。
    """

    def __init__(self, config: AppConfig | None = None, *, session_scope: SessionScope | None = None) -> None:
        self._config = config or get_config()
        if not self._config.model_list:
            raise ValueError("config.yaml 中缺少 model_list 配置")
        self._router: Router | None = None
        self._model: ChatLiteLLMRouter | None = None
        self._session_scope = session_scope or _default_session_scope()

    # ------------------------------------------------------------------
    # 属性（懒加载）
    # ------------------------------------------------------------------

    @property
    def router(self) -> Router:
        """原始 litellm.Router 实例。"""
        if self._router is None:
            logger.info(
                "构建 LiteLLM Router",
                model_count=len(self._config.model_list),
                default_model=self._config.llm.default_model,
            )
            self._router = Router(model_list=self._config.model_list)
        return self._router

    @property
    def model(self) -> ChatLiteLLMRouter:
        """LangChain BaseChatModel 实例（ChatLiteLLMRouter）。"""
        if self._model is None:
            self._model = ChatLiteLLMRouter(
                router=self.router,
                model=self._config.llm.default_model,
            )
        return self._model

    @property
    def default_model(self) -> str:
        """当前默认模型名。"""
        return self._config.llm.default_model

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> AIMessage:
        """同步调用，返回完整 AIMessage（含 usage_metadata / response_metadata / tool_calls）。

        内部桥接到 ainvoke（asyncio.run）：保证 litellm smart-router
        （auto_router/complexity_router）的 pre-routing 生效。
        """
        return _run_async(self.ainvoke(messages, **kwargs))

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> AIMessage:
        """异步调用，返回完整 AIMessage。"""
        start = perf_counter()
        try:
            response = await self.model.ainvoke(messages, **kwargs)
            self._record_usage(_model_of(response), "ainvoke", _usage_of(response), duration_ms=_elapsed_ms(start))
            return response
        except Exception as e:
            self._record_usage(self.default_model, "ainvoke", None, success=False, error_message=str(e))
            raise

    def stream(self, messages: list[BaseMessage], **kwargs: Any) -> Iterator[BaseMessage]:
        """同步流式，逐 chunk 产出 AIMessageChunk（含 content / tool_call_chunks / usage_metadata）。

        内部桥接到 astream（同步生成器包装异步生成器）：保证
        smart-router pre-routing 生效。
        """
        agenerator = self.astream(messages, **kwargs)

        def _consume() -> Iterator[BaseMessage]:
            try:
                while True:
                    chunk = _run_async(agenerator.__anext__())
                    yield chunk
            except StopAsyncIteration:
                return

        yield from _consume()

    async def astream(self, messages: list[BaseMessage], **kwargs: Any) -> AsyncIterator[BaseMessage]:
        """异步流式，逐 chunk 产出 AIMessageChunk。"""
        async for chunk in self._astream_tracked(messages, None, **kwargs):
            yield chunk

    async def astream_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        *,
        space_id: int | str | None = None,
        conversation_id: int | None = None,
        run_id: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[BaseMessage]:
        """绑定工具后异步流式，并**记录每次调用的 token 与成本**。

        这是 Agent 运行时唯一该走的入口：``bind_tools`` + ``astream`` + 埋点
        必须在同一处完成。调用方自行 ``model.bind_tools(t).astream(...)``
        会绕过统计——这正是重构前对话链路零 ``llm_log`` 的原因。

        Args:
            messages: 消息列表
            tools: 工具列表；为空时**不**调用 bind_tools（部分 provider 拒绝空数组）
            space_id: 归因到的空间
            conversation_id: 归因到的会话
            run_id: 归因到的执行记录（agent_run.id），让成本能按轮次聚合
            **kwargs: 透传给底层 astream

        Yields:
            AIMessageChunk
        """
        bound = self.model.bind_tools(tools) if tools else self.model
        async for chunk in self._astream_tracked(
            messages,
            bound,
            space_id=space_id,
            conversation_id=conversation_id,
            run_id=run_id,
            request_type="tools",
            **kwargs,
        ):
            yield chunk

    async def _astream_tracked(
        self,
        messages: list[BaseMessage],
        bound: Any | None,
        *,
        space_id: int | str | None = None,
        conversation_id: int | None = None,
        run_id: int | None = None,
        request_type: str = "astream",
        **kwargs: Any,
    ) -> AsyncIterator[BaseMessage]:
        """流式调用 + 统计落库的公共实现。

        ``bound`` 为 None 时直接用底层 model（不绑工具）。
        """
        chat = bound if bound is not None else self.model
        start = perf_counter()
        tracker = _UsageTracker()
        try:
            async for chunk in chat.astream(messages, **kwargs):
                tracker.observe(chunk)
                yield chunk
            self._record_usage(
                tracker.model_name,
                request_type,
                tracker.usage,
                duration_ms=_elapsed_ms(start),
                space_id=space_id,
                conversation_id=conversation_id,
                run_id=run_id,
                routing_tier=tracker.tier,
            )
        except Exception as e:
            self._record_usage(
                tracker.model_name or self.default_model,
                request_type,
                tracker.usage,
                success=False,
                error_message=str(e),
                duration_ms=_elapsed_ms(start),
                space_id=space_id,
                conversation_id=conversation_id,
                run_id=run_id,
                routing_tier=tracker.tier,
            )
            raise

    # ------------------------------------------------------------------
    # 工具调用
    # ------------------------------------------------------------------

    def invoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        **kwargs: Any,
    ) -> AIMessage:
        """同步调用并绑定工具，返回 AIMessage（含 .tool_calls）。

        内部桥接到 ainvoke_with_tools：保证 smart-router pre-routing 生效。
        """
        return _run_async(self.ainvoke_with_tools(messages, tools, **kwargs))

    async def ainvoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        **kwargs: Any,
    ) -> AIMessage:
        """异步调用并绑定工具，返回 AIMessage（含 .tool_calls）。"""
        start = perf_counter()
        try:
            model_with_tools = self.model.bind_tools(tools)
            response = await model_with_tools.ainvoke(messages, **kwargs)
            self._record_usage(_model_of(response), "tools", _usage_of(response), duration_ms=_elapsed_ms(start))
            return response
        except Exception as e:
            self._record_usage(self.default_model, "tools", None, success=False, error_message=str(e))
            raise

    # ------------------------------------------------------------------
    # 观测
    # ------------------------------------------------------------------

    def get_model_names(self) -> list[str]:
        """返回 Router 中配置的全部模型名。"""
        return self.router.get_model_names()

    def count_tokens(self, messages: list[BaseMessage]) -> int:
        """预估给定消息的 token 数（不调用 API）。"""
        from litellm import token_counter

        # token_counter 接受 OpenAI 格式，转换一下
        openai_messages = [{"role": _get_role(m), "content": m.content} for m in messages]
        return token_counter(model=self.default_model, messages=openai_messages)

    # ------------------------------------------------------------------
    # LLM 调用统计落库
    # ------------------------------------------------------------------

    def _record_usage(
        self,
        model_name: str,
        request_type: str,
        usage: dict | None,
        *,
        success: bool = True,
        error_message: str = "",
        duration_ms: int = 0,
        space_id: int | str | None = None,
        conversation_id: int | None = None,
        run_id: int | None = None,
        routing_tier: str = "",
    ) -> None:
        """将一次 LLM 调用的 token / 模型 / 成本写入 ``llm_log`` 表。

        Args:
            model_name: 实际命中的模型（如 zai/glm-4-flash）。
                注意**不是** Router 的 model_group（smart-router）——后者无法算成本。
            request_type: 调用类型（invoke/ainvoke/stream/astream/tools）
            usage: litellm usage_metadata dict，可为 None
            success: 是否成功
            error_message: 失败原因
            duration_ms: 耗时毫秒
            space_id: 归因空间
            conversation_id: 归因会话
            run_id: 归因执行记录（agent_run.id）
            routing_tier: smart-router 决策档位
        """
        usage = usage or {}
        prompt_tokens = int(usage.get("input_tokens", 0) or 0)
        completion_tokens = int(usage.get("output_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0) or (prompt_tokens + completion_tokens)
        resolved_model = model_name or self.default_model

        try:
            from src.data.models.llm_log import LLMLog

            with self._session_scope() as session:
                session.add(
                    LLMLog(
                        model_name=resolved_model,
                        provider=resolved_model.split("/", 1)[0] if "/" in resolved_model else "",
                        request_type=request_type,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        duration_ms=int(duration_ms),
                        success=1 if success else 0,
                        error_message=(error_message or "")[:500],
                        space_id=_as_int(space_id),
                        conversation_id=_as_int(conversation_id),
                        run_id=_as_int(run_id),
                        routing_tier=routing_tier or "",
                        cost_usd=_estimate_cost(
                            resolved_model, prompt_tokens, completion_tokens, self._config.pricing
                        ),
                    )
                )
                session.commit()
        except Exception as e:  # 统计失败不影响主流程
            logger.warning("LLM 调用统计落库失败: %s", e)


@dataclass
class _UsageTracker:
    """流式过程中累积「最后一次非空的」usage / 模型名 / 路由档位。

    为什么是「最后一次非空」而不是「只看最后一块」：usage 通常挂在末尾的
    独立 chunk 上，但部分 provider 会提前返回，末尾反而是空 chunk。
    末块判定会静默漏记，累积判定更稳。
    """

    usage: dict = field(default_factory=dict)
    model_name: str = ""
    tier: str = ""

    def observe(self, chunk: BaseMessage | None) -> None:
        if chunk is None:
            return
        usage = getattr(chunk, "usage_metadata", None)
        if usage:
            self.usage = dict(usage)
        name = _model_of(chunk)
        if name:
            self.model_name = name
        tier = _routing_tier_of(chunk)
        if tier:
            self.tier = tier


def _model_of(message: BaseMessage | None) -> str:
    """提取**实际命中的模型**（而非 Router 的 model_group）。

    litellm Router 的 ``response_metadata`` 形如::

        {"model_group": "smart-router",          # ← 逻辑路由名，算不出成本
         "deployment": "zai/glm-4-flash",        # ← 真正花钱的模型
         "deployment_model_name": "glm-4-flash",
         "routing_decision": {"routed_model": "glm-4-flash", "tier": "SIMPLE"}}

    优先级：``deployment`` → ``routing_decision.routed_model`` →
    ``deployment_model_name`` → ``model_name`` / ``model``。
    """
    if message is None:
        return ""
    meta = getattr(message, "response_metadata", None) or {}

    deployment = meta.get("deployment")
    if isinstance(deployment, str) and deployment:
        return deployment

    routing = meta.get("routing_decision")
    if isinstance(routing, dict):
        routed = routing.get("routed_model")
        if isinstance(routed, str) and routed:
            return routed

    for key in ("deployment_model_name", "model_name", "model"):
        value = meta.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _routing_tier_of(message: BaseMessage | None) -> str:
    """提取 smart-router 的决策档位（SIMPLE / MEDIUM / COMPLEX / REASONING）。"""
    if message is None:
        return ""
    meta = getattr(message, "response_metadata", None) or {}
    routing = meta.get("routing_decision")
    if not isinstance(routing, dict):
        return ""
    tier = routing.get("tier")
    return str(tier) if tier else ""


def _lookup_pricing(model_name: str, pricing: list[Any] | None = None) -> dict | None:
    """查模型费率：先看 ``config.pricing`` 自定义表，再查 litellm 内置定价表。

    自定义表优先，因为 litellm 不收录的厂商（``zai/*``）只能靠用户补。
    返回的 dict 至少含 ``input_cost_per_token`` / ``output_cost_per_token``。
    """
    # 1) 自定义费率（config.pricing）
    for entry in pricing or []:
        name = entry.get("model") if isinstance(entry, dict) else getattr(entry, "model", None)
        if name != model_name:
            continue
        if isinstance(entry, dict):
            return entry
        return entry.model_dump() if hasattr(entry, "model_dump") else None

    # 2) litellm 内置定价表（两级：带 provider 前缀 / 裸名）
    try:
        import litellm

        cost_map = getattr(litellm, "model_cost", None) or {}
    except Exception:
        return None

    candidates = [model_name]
    if "/" in model_name:
        candidates.append(model_name.split("/", 1)[1])

    for key in candidates:
        info = cost_map.get(key)
        if isinstance(info, dict):
            return info
    return None


def _estimate_cost(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing: list[Any] | None = None,
) -> float | None:
    """按定价表估算本次调用成本（美元）。

    **算不出时返回 None，不返回 0**：0 会被下游当成「免费」，
    而 NULL 表示「未知」，两者在成本报表里含义完全不同。

    实现上**直接查定价表而不调 ``cost_per_token``**：后者会先做 provider
    解析，同一模型在「远端表加载成功 / 失败」两种状态下行为不一致
    （实测 ``zai/glm-4-flash`` 会从抛异常变成返回 ``0.0``），
    无法作为「有没有定价」的可靠判据。
    """
    if not model_name or (prompt_tokens <= 0 and completion_tokens <= 0):
        return None

    info = _lookup_pricing(model_name, pricing)
    if info is None:  # 定价表未收录该模型 → 成本未知
        return None

    input_rate = info.get("input_cost_per_token")
    output_rate = info.get("output_cost_per_token")
    if input_rate is None and output_rate is None:
        return None

    total = float(input_rate or 0) * prompt_tokens + float(output_rate or 0) * completion_tokens
    return round(total, 8)


def _as_int(value: int | str | None) -> int | None:
    """归因 ID 归一化为 int；非数字（如测试用的占位串）返回 None，避免入库炸列类型。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usage_of(message: BaseMessage | None) -> dict:
    """从 AIMessage 提取 usage_metadata dict。"""
    if message is None:
        return {}
    usage = getattr(message, "usage_metadata", None)
    return dict(usage) if usage else {}


def _elapsed_ms(start: float) -> int:
    """返回自 start 起的耗时（毫秒）。"""
    return int((perf_counter() - start) * 1000)


def _get_role(msg: BaseMessage) -> str:
    """从 BaseMessage 提取 role 字符串。"""
    return msg.type if msg.type in ("human", "ai", "system") else "user"


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_service: LLMService | None = None


def get_llm_service(config: AppConfig | None = None) -> LLMService:
    """获取全局 LLMService 单例。"""
    global _service
    if _service is None:
        _service = LLMService(config)
    return _service


def reset_llm_service() -> None:
    """重置全局单例（测试/热重载用）。"""
    global _service
    _service = None
