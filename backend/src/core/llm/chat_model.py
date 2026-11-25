"""langchain-litellm 适配层补丁。

适配器把 ``response_metadata`` 覆盖成路由组名，并在默认参数里固定携带
``stream=self.streaming``：前者让流式路径丢掉归因，后者让显式
``stream=False`` 仍请求流式。本模块用子类把两处都纠正。
"""

from collections.abc import AsyncIterator, Mapping
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_litellm import ChatLiteLLMRouter

#: litellm Router 在预路由阶段就地写入调用方 ``metadata`` 的归因键。
#: 适配层只透传该 dict、不读回，因此需要在模型侧显式取用。
_ROUTING_METADATA_KEYS = ("deployment", "deployment_model_name", "model_group", "routing_decision")


def _merge_routing_metadata(message: BaseMessage, metadata: Any) -> None:
    """把 litellm 就地填充的归因键合并进 ``response_metadata``。

    就地修改 ``message``；metadata 不是 dict 或尚未填充时不做任何事。

    Args:
        message: 待回填的完整响应或流式分片
        metadata: 传给 ``Router.acompletion`` 的 metadata，调用后由 litellm 补全
    """
    if not isinstance(metadata, dict):
        return
    patch = {key: metadata[key] for key in _ROUTING_METADATA_KEYS if metadata.get(key)}
    if patch:
        message.response_metadata = {**message.response_metadata, **patch}


class MetadataChatLiteLLMRouter(ChatLiteLLMRouter):
    """补回路由归因，并让 ``stream`` 按调用方意图生效。

    ``streaming=True`` 必须由构造方显式传入：langchain-core 依据
    ``model_fields_set`` 判定是否流式，字段默认值不参与 ``_should_stream``；
    漏传会回退 ``ainvoke``，``astream`` 只产出一个整体分片。
    """

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """流式产出分片，并在产出前回填本次路由元数据。

        Args:
            messages: LangChain 消息列表
            stop: 停止词
            run_manager: 回调管理器
            **kwargs: 透传给父类；``metadata`` 会被 litellm 就地填充

        Yields:
            带归因键的 ``response_metadata`` 的分片
        """
        metadata = kwargs.get("metadata")
        if not isinstance(metadata, dict):
            metadata = kwargs["metadata"] = {}
        async for generation in super()._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
            _merge_routing_metadata(generation.message, metadata)
            yield generation

    @property
    def _default_params(self) -> dict[str, Any]:
        """移除父类的 ``stream`` 默认值，避免覆盖调用方的显式选择。

        父类把 ``self.streaming`` 写进默认参数，显式 ``stream=False`` 的调用仍会以
        ``stream=True`` 请求 Router，随后把异步流当成完整响应解析。
        """
        params = super()._default_params
        params.pop("stream", None)
        return params

    def _create_chat_result(self, response: Mapping[str, Any], **params: Any) -> ChatResult:
        """非流式响应同样回填归因；仅在显式 ``stream=False`` 时走到。"""
        result = super()._create_chat_result(response, **params)
        for generation in result.generations:
            _merge_routing_metadata(generation.message, params.get("metadata"))
        return result
