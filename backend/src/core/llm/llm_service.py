"""基于 LiteLLM Router 的 LLM 服务。

所有调用经 Router 转发并写入 llm_log 统计；模型路由由 ``config.model_list`` 驱动。
"""

import os

# 只使用随包分发的本地定价表，不拉取远端 cost map：离线环境会阻塞到超时，
# 且远端表与本地表不一致时同一模型的成本会在「异常」与 0.0 之间漂移，而 0.0 会被读成免费。
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
    """返回默认会话工厂，取自全局数据库管理器。

    惰性构造，创建时不会触发数据库初始化。
    """

    @contextmanager
    def _scope() -> Iterator[Session]:
        from src.core.database.database_manager import init_database_from_config

        with init_database_from_config().get_session() as session:
            yield session

    return _scope


def _run_async(coro) -> Any:
    """在同步上下文中执行协程。

    smart-router 只在 ``Router.acompletion`` 的异步 pre-routing 阶段生效；
    当前线程已有事件循环时改投新线程执行，避免 ``asyncio.run`` 报错。

    Args:
        coro: 待执行的协程对象

    Returns:
        协程的返回值
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


class LLMService:
    """基于 LiteLLM Router 的统一 LLM 服务。

    内部持有 ``ChatLiteLLMRouter``，每次调用都会写入 llm_log 统计。

    Args:
        config: 应用配置；None 时取全局配置
        session_scope: 统计落库的会话工厂；None 时用全局数据库单例

    Raises:
        ValueError: ``config.model_list`` 为空
    """

    def __init__(self, config: AppConfig | None = None, *, session_scope: SessionScope | None = None) -> None:
        self._config = config or get_config()
        if not self._config.model_list:
            raise ValueError("config.yaml 中缺少 model_list 配置")
        self._router: Router | None = None
        self._model: ChatLiteLLMRouter | None = None
        self._session_scope = session_scope or _default_session_scope()

    # 属性（懒加载）

    @property
    def router(self) -> Router:
        """返回 ``litellm.Router``，首次访问时按 ``model_list`` 构建。"""
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
        """返回 LangChain 模型实例，首次访问时构建。"""
        if self._model is None:
            self._model = ChatLiteLLMRouter(
                router=self.router,
                model=self._config.llm.default_model,
            )
        return self._model

    @property
    def default_model(self) -> str:
        """返回当前默认模型名。"""
        return self._config.llm.default_model

    # 核心接口

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> AIMessage:
        """同步调用，返回完整响应。

        内部桥接到 ``ainvoke``：smart-router 的 pre-routing 只在异步路径生效。

        Args:
            messages: LangChain 消息列表
            **kwargs: 透传给底层 ``ainvoke``

        Returns:
            含 usage、response_metadata 与 tool_calls 的响应
        """
        return _run_async(self.ainvoke(messages, **kwargs))

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> AIMessage:
        """异步调用，返回完整响应。

        副作用：向 llm_log 写入一条统计记录，失败同样记录。

        Args:
            messages: LangChain 消息列表
            **kwargs: 透传给底层 ``ainvoke``

        Returns:
            模型响应
        """
        start = perf_counter()
        try:
            response = await self.model.ainvoke(messages, **kwargs)
            self._record_usage(_model_of(response), "ainvoke", _usage_of(response), duration_ms=_elapsed_ms(start))
            return response
        except Exception as e:
            self._record_usage(self.default_model, "ainvoke", None, success=False, error_message=str(e))
            raise

    def stream(self, messages: list[BaseMessage], **kwargs: Any) -> Iterator[BaseMessage]:
        """同步流式调用，逐块产出响应。

        内部把异步生成器包装为同步生成器，逐次桥接事件循环。

        Args:
            messages: LangChain 消息列表
            **kwargs: 透传给底层 ``astream``

        Yields:
            响应块，含 content、tool_call_chunks 与 usage_metadata
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
        """异步流式调用，逐块产出响应并记录统计。

        Yields:
            响应块
        """
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
        """绑定工具后异步流式调用，并记录 token 与成本。

        ``bind_tools``、``astream`` 与埋点必须同处完成，调用方自行绑定会绕过统计。

        Args:
            messages: LangChain 消息列表
            tools: 工具列表；为空时不调用 ``bind_tools``（部分 provider 拒绝空数组）
            space_id: 归因空间
            conversation_id: 归因会话
            run_id: 归因执行记录 ``agent_run.id``
            **kwargs: 透传给底层 ``astream``

        Yields:
            响应块
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
        """流式调用并落统计的公共实现。

        Args:
            messages: LangChain 消息列表
            bound: 已绑定工具的模型；None 时直接使用底层模型
            space_id: 归因空间
            conversation_id: 归因会话
            run_id: 归因执行记录
            request_type: 写入统计的调用类型
            **kwargs: 透传给底层 ``astream``

        Yields:
            响应块

        Raises:
            异常原样上抛：先记录失败统计再抛出。
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

    # 工具调用

    def invoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        **kwargs: Any,
    ) -> AIMessage:
        """同步调用并绑定工具。

        内部桥接到 ``ainvoke_with_tools``：smart-router 的 pre-routing 只在异步路径生效。

        Args:
            messages: LangChain 消息列表
            tools: 工具列表
            **kwargs: 透传给底层 ``ainvoke``

        Returns:
            含 tool_calls 的响应
        """
        return _run_async(self.ainvoke_with_tools(messages, tools, **kwargs))

    async def ainvoke_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[Any],
        **kwargs: Any,
    ) -> AIMessage:
        """异步调用并绑定工具。

        副作用：向 llm_log 写入一条统计记录。

        Args:
            messages: LangChain 消息列表
            tools: 工具列表
            **kwargs: 透传给底层 ``ainvoke``

        Returns:
            含 tool_calls 的响应
        """
        start = perf_counter()
        try:
            model_with_tools = self.model.bind_tools(tools)
            response = await model_with_tools.ainvoke(messages, **kwargs)
            self._record_usage(_model_of(response), "tools", _usage_of(response), duration_ms=_elapsed_ms(start))
            return response
        except Exception as e:
            self._record_usage(self.default_model, "tools", None, success=False, error_message=str(e))
            raise

    # 观测

    def get_model_names(self) -> list[str]:
        """返回 Router 中配置的全部模型名。"""
        return self.router.get_model_names()

    def count_tokens(self, messages: list[BaseMessage]) -> int:
        """预估消息的 token 数，不发起 API 调用。

        Args:
            messages: LangChain 消息列表

        Returns:
            预估 token 数
        """
        from litellm import token_counter

        # litellm.token_counter 只接受 OpenAI 消息格式
        openai_messages = [{"role": _get_role(m), "content": m.content} for m in messages]
        return token_counter(model=self.default_model, messages=openai_messages)

    # LLM 调用统计落库

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
        """将一次调用的 token、模型与成本写入 ``llm_log`` 表。

        副作用：写库并提交；落库失败只记告警，不影响主流程。

        Args:
            model_name: 实际命中的模型，如 ``zai/glm-4-flash``；不能传 Router 的路由名，
                后者无法计价
            request_type: 调用类型，取值 ``invoke`` / ``ainvoke`` / ``stream`` / ``astream`` / ``tools``
            usage: litellm 的 usage dict，可为 None
            success: 调用是否成功
            error_message: 失败原因，入库前截断到 500 字符
            duration_ms: 耗时毫秒
            space_id: 归因空间
            conversation_id: 归因会话
            run_id: 归因执行记录
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
    """流式过程中累积最近一次非空的 usage、模型名与路由档位。

    usage 通常挂在末尾的独立块上，但部分 provider 会提前返回、末尾反而是空块，
    因此按「最后一次非空」累积，避免漏记。
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
    """提取实际命中的模型名。

    Router 的 ``response_metadata.model_group`` 是逻辑路由名、无法计价，
    故按 ``deployment`` → ``routing_decision.routed_model`` →
    ``deployment_model_name`` → ``model_name`` / ``model`` 的顺序取。

    Args:
        message: 模型响应，可为 None

    Returns:
        模型名；取不到时返回空串
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
    """提取 smart-router 的决策档位，如 ``SIMPLE`` / ``COMPLEX``。

    Returns:
        档位名；缺失时返回空串
    """
    if message is None:
        return ""
    meta = getattr(message, "response_metadata", None) or {}
    routing = meta.get("routing_decision")
    if not isinstance(routing, dict):
        return ""
    tier = routing.get("tier")
    return str(tier) if tier else ""


def _lookup_pricing(model_name: str, pricing: list[Any] | None = None) -> dict | None:
    """查模型费率，先看 ``config.pricing``，再查 litellm 内置定价表。

    自定义表优先：litellm 未收录的厂商模型只能在此补充。

    Args:
        model_name: 模型名，可带 provider 前缀
        pricing: 自定义费率列表，元素为 dict 或 ``ModelPricing``

    Returns:
        含 ``input_cost_per_token`` / ``output_cost_per_token`` 的费率 dict；
        未收录时返回 None
    """
    # 1) 自定义费率（config.pricing）
    for entry in pricing or []:
        name = entry.get("model") if isinstance(entry, dict) else getattr(entry, "model", None)
        if name != model_name:
            continue
        if isinstance(entry, dict):
            return entry
        return entry.model_dump() if hasattr(entry, "model_dump") else None

    # 2) litellm 内置定价表：先按带前缀的完整名，再按裸模型名
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

    无法计价时返回 None 而非 0.0：NULL 表示未知，0.0 会被下游当成免费。
    直接查定价表而不调 ``cost_per_token``，后者对未收录模型的行为随远端表状态变化。

    Args:
        model_name: 模型名
        prompt_tokens: 输入 token 数
        completion_tokens: 输出 token 数
        pricing: 自定义费率列表

    Returns:
        成本（美元，保留 8 位小数）；无法计价时返回 None
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
    """把归因 ID 归一化为 int。

    非数字值（如测试占位串）返回 None，避免写入列时类型冲突。
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usage_of(message: BaseMessage | None) -> dict:
    """提取消息的 ``usage_metadata``。

    Returns:
        usage dict；缺失时返回空 dict
    """
    if message is None:
        return {}
    usage = getattr(message, "usage_metadata", None)
    return dict(usage) if usage else {}


def _elapsed_ms(start: float) -> int:
    """返回自 start 起的耗时（毫秒）。"""
    return int((perf_counter() - start) * 1000)


def _get_role(msg: BaseMessage) -> str:
    """返回 OpenAI 消息角色名，无法识别时按 ``user`` 处理。"""
    return msg.type if msg.type in ("human", "ai", "system") else "user"


# 全局单例

_service: LLMService | None = None


def get_llm_service(config: AppConfig | None = None) -> LLMService:
    """返回全局服务单例，首次调用时创建。

    Args:
        config: 应用配置；仅首次创建时生效

    Returns:
        全局唯一的 ``LLMService``
    """
    global _service
    if _service is None:
        _service = LLMService(config)
    return _service


def reset_llm_service() -> None:
    """清除全局服务单例，供测试与热重载使用。"""
    global _service
    _service = None
