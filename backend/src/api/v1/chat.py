"""对话流式路由，统一 SSE 协议。

模式差异由工具白名单保证：``ask`` / ``plan`` 的工具列表中不含副作用工具，
而非依赖提示词约束。会话与 user 消息在流开始前落库，
会话 ID 通过响应头 ``X-Conversation-Id`` 返回。
"""

from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from src.agent.events import ErrorEvent, render
from src.core.logging import get_logger
from src.data.schemas.conversation import ChatStreamRequest
from src.data.services.chat_stream_service import ChatStreamService

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["对话"])

SSE_MEDIA_TYPE = "text/event-stream; charset=utf-8"

# X-Accel-Buffering: no 必须设置，否则 nginx 会缓存整条流后一次性下发
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Access-Control-Expose-Headers": "X-Conversation-Id",
}


@router.post("/stream")
async def chat_stream(body: ChatStreamRequest) -> StreamingResponse:
    """执行一轮对话并以 SSE 流返回。

    副作用：落库会话与 user 消息，可能触发 agent 工具调用。

    Args:
        body: 对话请求体，含指令、空间、模式、所选 skill 与会话 ID

    Returns:
        ``text/event-stream`` 响应，帧格式为 ``id:`` / ``event:`` / ``data:``；
        缺少 ``space_id`` 时流内只返回一条 error 事件，HTTP 状态仍为 200
    """
    service = ChatStreamService()
    conversation_id = await run_in_threadpool(service.ensure_conversation, body)
    headers = {**_SSE_HEADERS, "X-Conversation-Id": str(conversation_id)}

    # 空间是硬前提：无空间则无工作目录、接口清单与环境，Agent 无法执行。
    # 这里返回 error 帧而非 400，前端已在读流，帧比 HTTP 状态码更易处理。
    if not body.space_id:
        logger.warning("对话缺少 space_id", conversation_id=conversation_id)
        return StreamingResponse(
            _missing_space_stream(),
            media_type=SSE_MEDIA_TYPE,
            headers=headers,
        )

    return StreamingResponse(
        service.stream_answer(body, conversation_id),
        media_type=SSE_MEDIA_TYPE,
        headers=headers,
    )


async def _missing_space_stream() -> AsyncIterator[str]:
    """输出缺少空间时的单帧错误事件流。"""
    yield render(ErrorEvent(message="请先选择一个测试空间后再开始对话。"), 0)
