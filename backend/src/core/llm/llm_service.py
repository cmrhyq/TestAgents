"""基于 LiteLLM Router 的统一 LLM 服务。

使用 ``langchain-litellm`` 的 ``ChatLiteLLMRouter`` 包装 ``litellm.Router``，
提供统一的 LangChain BaseChatModel 接口：invoke / stream / bind_tools / astream_events。

所有方法直接接收 ``list[BaseMessage]``。

配置来源：``config.model_list``（模型路由列表）+ ``config.llm.default_model``（默认模型名）。

用法::

    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from src.core.llm.llm_service import get_llm_service

    service = get_llm_service()

    # 基础调用（system + user 消息）
    response = service.invoke([
        SystemMessage(content="你是一个 API 测试助手"),
        HumanMessage(content="帮我测试登录接口"),
    ])
    print(response.content)           # 文本回答
    print(response.usage_metadata)    # {"input_tokens": N, "output_tokens": N, "total_tokens": N}

    # 多轮对话（含历史 assistant 消息）
    response = service.invoke([
        SystemMessage(content="你是一个 API 测试助手"),
        HumanMessage(content="帮我测试登录接口"),
        AIMessage(content="好的，我来帮你设计测试用例..."),
        HumanMessage(content="再加一个异常场景"),
    ])

    # 流式输出
    for chunk in service.stream([HumanMessage(content="解释什么是接口测试")]):
        print(chunk.content, end="")  # 逐 token 输出

    # 工具调用
    from langchain_core.tools import tool

    @tool
    def get_endpoints(space_id: int) -> str:
        \"\"\"查询空间下的接口列表。\"\"\"
        return "..."

    response = service.invoke_with_tools(
        [HumanMessage(content="查询空间 1 的接口")],
        tools=[get_endpoints],
    )
    print(response.tool_calls)        # [{"name": "get_endpoints", "args": {"space_id": 1}, ...}]
"""

from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any

import asyncio

from langchain_core.messages import AIMessage, BaseMessage
from langchain_litellm import ChatLiteLLMRouter
from litellm import Router

from src.core.config import AppConfig, get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


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

    所有方法接收 ``list[BaseMessage]``，返回 ``AIMessage`` 或 ``AIMessageChunk``。

    Args:
        config: 应用配置，为 None 时使用全局配置。

    Raises:
        ValueError: ``config.model_list`` 为空时。
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or get_config()
        if not self._config.model_list:
            raise ValueError("config.yaml 中缺少 model_list 配置")
        self._router: Router | None = None
        self._model: ChatLiteLLMRouter | None = None

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
        start = perf_counter()
        last_chunk: BaseMessage | None = None
        try:
            async for chunk in self.model.astream(messages, **kwargs):
                last_chunk = chunk
                yield chunk
            self._record_usage(_model_of(last_chunk), "astream", _usage_of(last_chunk), duration_ms=_elapsed_ms(start))
        except Exception as e:
            self._record_usage(self.default_model, "astream", _usage_of(last_chunk), success=False, error_message=str(e))
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
    ) -> None:
        """将一次 LLM 调用的 token / 模型统计写入 ``llm_log`` 表。

        Args:
            model_name: 实际使用的模型（如 zai/glm-4-flash）
            request_type: 调用类型（invoke/ainvoke/stream/astream/tools）
            usage: litellm usage_metadata dict，可为 None
            success: 是否成功
            error_message: 失败原因
            duration_ms: 耗时毫秒
        """
        usage = usage or {}
        try:
            from src.core.database.database_manager import init_database_from_config
            from src.data.models.llm_log import LLMLog

            with init_database_from_config().get_session() as session:
                session.add(
                    LLMLog(
                        model_name=model_name or self.default_model,
                        provider=(model_name or "").split("/", 1)[0],
                        request_type=request_type,
                        prompt_tokens=int(usage.get("input_tokens", 0) or 0),
                        completion_tokens=int(usage.get("output_tokens", 0) or 0),
                        total_tokens=int(usage.get("total_tokens", 0) or 0),
                        duration_ms=int(duration_ms),
                        success=1 if success else 0,
                        error_message=(error_message or "")[:500],
                    )
                )
                session.commit()
        except Exception as e:  # 统计失败不影响主流程
            logger.warning("LLM 调用统计落库失败: %s", e)


def _model_of(message: BaseMessage | None) -> str:
    """从 AIMessage 提取实际使用的模型名（response_metadata 兜底为空）。"""
    if message is None:
        return ""
    meta = getattr(message, "response_metadata", None) or {}
    return str(meta.get("model", "")) or ""


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
