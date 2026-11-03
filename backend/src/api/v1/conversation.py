"""会话管理路由：会话增删改查与消息列表。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.core.errors import NotFoundError
from src.data.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
)
from src.data.schemas.message import MessageListResponse, MessageResponse
from src.data.services import ConversationService

router = APIRouter(prefix="/conversations", tags=["会话管理"])


@router.post("/", response_model=ConversationResponse, status_code=201)
def create_conversation(body: ConversationCreate, db: Session = Depends(get_db)):
    """创建会话。

    Args:
        body: 所属空间、标题与工作模式
        db: 请求级数据库会话

    Returns:
        新建会话详情，HTTP 201
    """
    return ConversationService(db).create_conversation(body)


@router.get("/", response_model=ConversationListResponse)
def list_conversations(
    space_id: int | None = Query(default=None, description="按空间筛选"),
    status: int | None = Query(default=1, description="状态筛选: 1-正常, 0-删除"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """分页查询会话列表。

    Args:
        space_id: 按空间过滤，不传则跨空间查询
        status: 状态过滤，1 为正常、0 为已删除
        page: 页码，从 1 开始
        page_size: 每页条数，取值 1-100
        db: 请求级数据库会话

    Returns:
        当页会话列表与总数
    """
    conversations, total = ConversationService(db).list_conversations(space_id, status, page, page_size)
    return ConversationListResponse(
        items=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """查询会话详情，含全部消息。

    Args:
        conversation_id: 会话 ID
        db: 请求级数据库会话

    Returns:
        会话详情与消息列表

    Raises:
        NotFoundError: 会话不存在，返回 HTTP 404
    """
    conversation = ConversationService(db).get_with_messages(conversation_id)
    if conversation is None:
        raise NotFoundError("会话不存在")
    return ConversationDetail.model_validate(conversation)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
def list_messages(conversation_id: int, db: Session = Depends(get_db)):
    """查询会话的消息列表，按时间升序。

    Args:
        conversation_id: 会话 ID
        db: 请求级数据库会话

    Returns:
        消息列表与总数

    Raises:
        NotFoundError: 会话不存在，返回 HTTP 404
    """
    service = ConversationService(db)
    service.get_or_raise(conversation_id, "会话不存在")
    messages = service.list_messages(conversation_id)
    return MessageListResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        total=len(messages),
    )


@router.put("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: int, body: ConversationUpdate, db: Session = Depends(get_db)):
    """局部更新会话，可改标题、模式与状态。

    Args:
        conversation_id: 会话 ID
        body: 待更新字段
        db: 请求级数据库会话

    Returns:
        更新后的会话详情

    Raises:
        NotFoundError: 会话不存在，返回 HTTP 404
    """
    return ConversationService(db).update_conversation(conversation_id, body.model_dump(exclude_unset=True))


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """删除会话及其关联消息。

    Args:
        conversation_id: 会话 ID
        db: 请求级数据库会话

    Returns:
        无响应体，HTTP 204

    Raises:
        NotFoundError: 会话不存在，返回 HTTP 404
    """
    ConversationService(db).delete_conversation(conversation_id)
