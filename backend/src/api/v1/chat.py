"""对话流式路由（统一 SSE 协议，模式差异由工具白名单保证）。

**三种模式共用同一条流式路径**，区别只在 ``runner`` 拿到的工具集合：
``ask`` / ``plan`` 的列表里根本没有 ``send_request`` / ``write_file``，
所以模型不可能"违抗指令"去执行——这是执行路径上的硬拦截，
而不是 prompt 里写一句「请不要执行」。

会话与 user 消息在流式开始前落库（``ChatStreamService.ensure_conversation``），
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

# X-Accel-Buffering: no 必须设置——否则 nginx 会把整条流攒完再一次性吐出，流式失去意义
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Access-Control-Expose-Headers": "X-Conversation-Id",
}


@router.post("/stream")
async def chat_stream(body: ChatStreamRequest) -> StreamingResponse:
    """跑一轮对话并返回 SSE 流式响应。

    Args:
        body: 对话请求体（instruction / space_id / mode / skill_names / conversation_id）

    Returns:
        ``text/event-stream`` 响应，帧格式为 ``id:`` / ``event:`` / ``data:``
    """
    service = ChatStreamService()
    conversation_id = await run_in_threadpool(service.ensure_conversation, body)
    headers = {**_SSE_HEADERS, "X-Conversation-Id": str(conversation_id)}

    # 空间是硬前提：没有空间就没有工作目录、没有接口清单、没有环境，
    # Agent 什么都做不了。这里直接回一条 error 事件而不是 400——
    # 前端已经在读流了，帧比 HTTP 状态码更好处理。
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
    """缺少空间的提示流。"""
    yield render(ErrorEvent(message="请先选择一个测试空间后再开始对话。"), 0)
